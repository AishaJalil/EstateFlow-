import asyncio
import json
import logging
import re
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import get_settings
from app.services.issue_parser import parse_issue_fast, parse_urgency_fast

logger = logging.getLogger(__name__)

# Retry config for 429 rate-limit responses
_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_BASE_DELAY = 2.0  # seconds; doubles each retry (2 → 4 → 8)


def _build_client() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.openrouter_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        temperature=0.2,
        timeout=settings.llm_timeout_seconds,
        max_retries=0,
        default_headers={
            "HTTP-Referer": "https://estateflow.local",
            "X-Title": "EstateFlow",
        },
    )


async def _ollama_chat(system: str, user: str) -> str:
    settings = get_settings()
    timeout = httpx.Timeout(10.0, read=settings.llm_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": "json",
            },
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _estimate_tokens(system: str, user: str, response_text: str = "") -> int:
    return max(1, (len(system) + len(user) + len(response_text)) // 4)


def _tokens_from_response(response: Any, system: str, user: str, content: str) -> int:
    usage = getattr(response, "usage_metadata", None) or {}
    if isinstance(usage, dict) and usage.get("total_tokens"):
        return int(usage["total_tokens"])
    meta = getattr(response, "response_metadata", None) or {}
    tu = meta.get("token_usage") or meta.get("usage") or {}
    if isinstance(tu, dict):
        total = tu.get("total_tokens")
        if total:
            return int(total)
        inp = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        out = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
        if inp or out:
            return inp + out
    return _estimate_tokens(system, user, content)


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
        raise


async def structured_completion(
    system: str,
    user: str,
    *,
    fallback_issue: str | None = None,
    fallback_image_desc: str = "",
    fallback_risk_hits: list[str] | None = None,
    fallback_urgency_boost: str | None = None,
) -> dict[str, Any]:
    """
    Call OpenRouter with a hard timeout and exponential-backoff retry on 429.

    Retry schedule: up to 3 attempts, waiting 2s → 4s → 8s between them.
    Only falls back to rule-based parsing when all retries are exhausted or
    a non-rate-limit error occurs.
    """
    settings = get_settings()
    timeout = settings.llm_timeout_seconds

    async def _call_llm() -> tuple[dict[str, Any], int]:
        llm = _build_client()
        response = await llm.ainvoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        content = response.content
        if isinstance(content, list):
            content = "".join(str(c) for c in content)
        text = str(content)
        tokens = _tokens_from_response(response, system, user, text)
        return _extract_json(text), tokens

    last_exc: Exception | None = None

    for attempt in range(1, _RATE_LIMIT_RETRIES + 1):
        try:
            parsed, tokens = await asyncio.wait_for(_call_llm(), timeout=timeout)
            parsed["__llm_tokens"] = tokens
            return parsed

        except asyncio.TimeoutError:
            logger.warning("LLM timed out after %ss (attempt %d/%d)", timeout, attempt, _RATE_LIMIT_RETRIES)
            # Timeouts are not retried — fall through to fallback immediately
            last_exc = None
            break

        except Exception as exc:
            last_exc = exc
            err = str(exc).lower()
            is_rate_limit = "429" in err or "rate limit" in err or "too many requests" in err

            if is_rate_limit:
                if attempt < _RATE_LIMIT_RETRIES:
                    delay = _RATE_LIMIT_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "LLM rate-limited (attempt %d/%d) — retrying in %.1fs",
                        attempt, _RATE_LIMIT_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.warning(
                        "LLM rate-limited on all %d attempts — falling back", _RATE_LIMIT_RETRIES
                    )
            else:
                logger.warning("LLM failed (%s) — trying fallbacks", exc)

            # Non-rate-limit error: try Ollama immediately, then break
            if settings.use_ollama_fallback:
                try:
                    raw = await asyncio.wait_for(_ollama_chat(system, user), timeout=timeout)
                    parsed = _extract_json(raw)
                    parsed["__llm_tokens"] = _estimate_tokens(system, user, raw)
                    return parsed
                except Exception as ollama_exc:
                    logger.warning("Ollama fallback failed: %s", ollama_exc)

            if not is_rate_limit:
                break  # Don't retry non-429 errors

    # All retries exhausted — try Ollama once more for rate-limit case
    if last_exc is not None and settings.use_ollama_fallback:
        err = str(last_exc).lower()
        if "429" in err or "rate limit" in err or "too many requests" in err:
            try:
                raw = await asyncio.wait_for(_ollama_chat(system, user), timeout=timeout)
                parsed = _extract_json(raw)
                parsed["__llm_tokens"] = _estimate_tokens(system, user, raw)
                return parsed
            except Exception as ollama_exc:
                logger.warning("Ollama fallback failed after rate-limit retries: %s", ollama_exc)

    if fallback_issue is not None:
        if fallback_risk_hits is not None:
            fb = parse_urgency_fast(
                fallback_issue, fallback_risk_hits, fallback_urgency_boost
            )
            fb["__llm_tokens"] = 0
            return fb
        fb = parse_issue_fast(fallback_issue, fallback_image_desc)
        fb["__llm_tokens"] = 0
        return fb

    return {
        "summary": "Classification unavailable",
        "category": "General",
        "trade": "general",
        "vendor_specialty": "general",
        "confidence": 0.5,
        "source": "minimal_fallback",
    }