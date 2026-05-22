import re
from datetime import datetime, timedelta
from typing import Any

from app.services.llm import structured_completion

_DECLINE_PATTERNS = re.compile(
    r"\b(not available|unavailable|can't make|cannot make|decline|pass on|"
    r"unable to|won't be able|busy that day|sorry.{0,20}can't)\b",
    re.I,
)

# Specific patterns (high confidence — concrete date/time mentioned)
_SPECIFIC_TIME_PATTERNS = [
    r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b",       # 12/05/2024
    r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b",                # 10:30am
    r"\b(\d{1,2})\s*(am|pm)\b",                        # 10am
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(morning|afternoon|evening|at\s+\d)",  # Monday morning
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b.{0,20}\b\d{1,2}(am|pm|\s*:\s*\d{2})",  # Tuesday at 2pm
]

# Vague patterns (lower confidence — only day-of-week / today / tomorrow / time-of-day)
_VAGUE_TIME_PATTERNS = [
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(morning|afternoon|evening|noon)\b",
    r"\b(tomorrow|today)\b",
]

# Positive-intent words that, combined with a time hint, make it a clear accept
_ACCEPT_WORDS = re.compile(
    r"\b(confirm|confirmed|works|work for me|i'll be there|can do|available|see you|sounds good|okay|ok|yes|yep|sure|absolutely|perfect)\b",
    re.I,
)


def _extract_hour_from_text(lower: str) -> int:
    """Best-effort hour extraction from a vendor reply (UTC assumed)."""
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)\b", lower)
    if m:
        h = int(m.group(1))
        if m.group(3) == "pm" and h != 12:
            h += 12
        elif m.group(3) == "am" and h == 12:
            h = 0
        return h
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", lower)
    if m:
        h = int(m.group(1))
        if m.group(2) == "pm" and h != 12:
            h += 12
        elif m.group(2) == "am" and h == 12:
            h = 0
        return h
    if "morning" in lower:
        return 9
    if "noon" in lower:
        return 12
    if "afternoon" in lower:
        return 14
    if "evening" in lower:
        return 17
    return 10  # default


def _rule_parse(body: str) -> dict[str, Any]:
    text = body.strip()
    lower = text.lower()

    if _DECLINE_PATTERNS.search(lower):
        return {"intent": "decline", "scheduled_iso": None, "confidence": 0.9}

    has_specific = any(re.search(p, lower) for p in _SPECIFIC_TIME_PATTERNS)
    has_vague = any(re.search(p, lower) for p in _VAGUE_TIME_PATTERNS)
    has_accept_word = bool(_ACCEPT_WORDS.search(lower))

    if has_specific or (has_vague and has_accept_word):
        # Resolve base date
        base = datetime.utcnow() + timedelta(days=1)
        if "today" in lower:
            base = datetime.utcnow()
        elif "tomorrow" in lower:
            base = datetime.utcnow() + timedelta(days=1)
        else:
            # Map day-of-week to nearest upcoming occurrence
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            for i, day in enumerate(days):
                if re.search(rf"\b{day}\b", lower):
                    today_dow = datetime.utcnow().weekday()  # 0=Monday
                    delta = (i - today_dow) % 7 or 7
                    base = datetime.utcnow() + timedelta(days=delta)
                    break

        hour = _extract_hour_from_text(lower)
        scheduled = base.replace(hour=hour, minute=0, second=0, microsecond=0)
        confidence = 0.88 if has_specific else 0.75
        return {
            "intent": "accept",
            "scheduled_iso": scheduled.isoformat() + "Z",
            "confidence": confidence,
            "raw_time_text": text[:500],
        }

    if has_vague:
        # Vague time hint but no clear accept word — still likely an accept, use LLM to confirm
        base = datetime.utcnow() + timedelta(days=1)
        scheduled = base.replace(hour=10, minute=0, second=0, microsecond=0)
        return {
            "intent": "accept",
            "scheduled_iso": scheduled.isoformat() + "Z",
            "confidence": 0.55,  # below threshold → LLM will be consulted
            "raw_time_text": text[:500],
        }

    return {"intent": "unclear", "scheduled_iso": None, "confidence": 0.3}


async def parse_vendor_reply(body: str) -> dict[str, Any]:
    """Classify vendor reply: accept (with visit time), decline, or unclear.

    Flow:
      1. Rule-based fast parse.
      2. If confidence >= 0.7, return immediately — no LLM call.
      3. Otherwise call LLM for ambiguous cases (vague time, no accept word, unclear).
      4. On LLM failure fall back to the rule result.
    """
    rule = _rule_parse(body)
    if rule["confidence"] >= 0.7:
        return rule

    system = (
        "Parse a vendor's SMS-style reply about a maintenance visit. "
        "Return JSON only: intent (accept|decline|unclear), scheduled_iso (ISO8601 UTC or null), "
        "confidence (0-1). accept means they propose or confirm a visit day/time."
    )
    try:
        parsed = await structured_completion(system, f"Vendor message:\n{body}")
        intent = str(parsed.get("intent", "unclear")).lower()
        if intent not in ("accept", "decline", "unclear"):
            intent = "unclear"
        return {
            "intent": intent,
            "scheduled_iso": parsed.get("scheduled_iso"),
            "confidence": float(parsed.get("confidence") or 0.5),
            "raw_time_text": body[:500],
        }
    except Exception:
        return rule