"""WhatsApp notification service via TextMeBot API."""
import asyncio
import logging
from urllib.parse import quote

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

TEXTMEBOT_URL = "https://api.textmebot.com/send.php"


def _normalize_phone(phone: str) -> str:
    """Normalize Pakistani phone numbers to international format (e.g. 03001234567 → 923001234567)."""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        p = p[1:]
    if p.startswith("0") and len(p) == 11:
        # Pakistani local format → international
        p = "92" + p[1:]
    return p


async def send_whatsapp(
    phone: str,
    message: str,
    *,
    doc_url: str | None = None,
    image_url: str | None = None,
    delay_seconds: int = 5,
) -> bool:
    """
    Send a WhatsApp message via TextMeBot.

    Args:
        phone: Recipient phone number (any common format, auto-normalized).
        message: Plain text message (URL-encoded automatically).
        doc_url: Optional PDF/document URL to attach.
        image_url: Optional image URL to attach.
        delay_seconds: Mandatory delay before sending (TextMeBot anti-ban). Default 5s.

    Returns:
        True if the API call succeeded, False otherwise (never raises).
    """
    settings = get_settings()
    if not settings.textmebot_api_key:
        logger.debug("TextMeBot API key not configured — WhatsApp notification skipped.")
        return False

    normalized = _normalize_phone(phone)
    if not normalized:
        logger.warning("WhatsApp: invalid phone number '%s' — skipped.", phone)
        return False

    # Mandatory delay to avoid WhatsApp rate-limiting / bans
    await asyncio.sleep(delay_seconds)

    params: dict[str, str] = {
        "recipient": normalized,
        "apikey": settings.textmebot_api_key,
        "text": quote(message, safe=""),
        "json": "yes",
    }
    if doc_url:
        params["document"] = doc_url
    elif image_url:
        params["file"] = image_url

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(TEXTMEBOT_URL, params=params)
            if resp.status_code == 200:
                logger.info("WhatsApp sent to %s", normalized)
                return True
            logger.warning(
                "TextMeBot returned HTTP %s for %s: %s",
                resp.status_code, normalized, resp.text[:200],
            )
            return False
    except Exception as exc:
        logger.error("WhatsApp send failed for %s: %s", normalized, exc)
        return False


async def send_whatsapp_to_managers(
    message: str,
    *,
    doc_url: str | None = None,
) -> int:
    """Send a WhatsApp message to all managers/admins who have a whatsapp_phone set."""
    from app.db import get_supabase_admin

    admin = get_supabase_admin()
    managers = (
        admin.table("profiles")
        .select("whatsapp_phone")
        .in_("role", ["manager", "admin"])
        .not_.is_("whatsapp_phone", "null")
        .execute()
    )
    sent = 0
    for m in managers.data or []:
        phone = (m.get("whatsapp_phone") or "").strip()
        if phone:
            ok = await send_whatsapp(phone, message, doc_url=doc_url)
            if ok:
                sent += 1
    return sent
