"""Google Calendar — per-tenant (profile) or per-vendor OAuth in calendar_connections."""

import logging
from datetime import datetime, timedelta
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.db import get_supabase_admin
from app.services.calendar_tokens import connection_row_to_credentials, encrypt_token

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _parse_dt(scheduled_iso: str | None) -> datetime:
    """Always returns a naive UTC datetime for consistent isoformat() output."""
    if not scheduled_iso:
        return datetime.utcnow() + timedelta(days=1)
    raw = scheduled_iso.strip()
    # Normalise: strip trailing Z, convert +00:00 offset to naive UTC
    raw = raw.rstrip("Z").replace("+00:00", "").replace("+0000", "")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return datetime.utcnow() + timedelta(days=1)


def _get_connection_for_profile(profile_id: str) -> dict[str, Any] | None:
    admin = get_supabase_admin()
    row = (
        admin.table("calendar_connections")
        .select("*")
        .eq("profile_id", profile_id)
        .eq("provider", "google")
        .limit(1)
        .execute()
    )
    return row.data[0] if row.data else None


def _get_connection_for_vendor(vendor_id: str) -> dict[str, Any] | None:
    admin = get_supabase_admin()
    row = (
        admin.table("calendar_connections")
        .select("*")
        .eq("vendor_id", vendor_id)
        .eq("provider", "google")
        .limit(1)
        .execute()
    )
    return row.data[0] if row.data else None


def profile_has_calendar(profile_id: str) -> bool:
    return _get_connection_for_profile(profile_id) is not None


def vendor_has_calendar(vendor_id: str) -> bool:
    return _get_connection_for_vendor(vendor_id) is not None


def calendar_connected_for_user(user: dict[str, Any]) -> bool:
    if user.get("auth_type") == "vendor":
        return vendor_has_calendar(user["vendor_id"])
    return profile_has_calendar(user["id"])


def _persist_refreshed_tokens(conn: dict[str, Any], creds: Credentials) -> None:
    admin = get_supabase_admin()
    # creds.expiry is naive UTC after _build_credentials normalisation
    expiry = (creds.expiry.isoformat() + "Z") if creds.expiry else None
    payload = {
        "access_token_enc": encrypt_token(creds.token or ""),
        "token_expiry": expiry,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if conn.get("vendor_id"):
        admin.table("calendar_connections").update(payload).eq("vendor_id", conn["vendor_id"]).execute()
    else:
        admin.table("calendar_connections").update(payload).eq("profile_id", conn["profile_id"]).execute()


def _build_credentials(conn: dict[str, Any]) -> Credentials:
    settings = get_settings()
    creds_data = connection_row_to_credentials(conn)
    creds = Credentials(
        token=creds_data["access_token"],
        refresh_token=creds_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=SCOPES,
    )
    if creds_data.get("token_expiry"):
        try:
            raw = str(creds_data["token_expiry"]).replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            # google-auth compares expiry against a naive UTC datetime internally,
            # so strip tzinfo after converting to UTC to avoid offset-naive vs
            # offset-aware TypeError on creds.expired.
            if dt.tzinfo is not None:
                from datetime import timezone as _tz
                dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
            creds.expiry = dt
        except ValueError:
            pass
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _persist_refreshed_tokens(conn, creds)
    return creds


def _create_event(conn: dict[str, Any], *, summary: str, start_iso: str | None, end_iso: str | None, description: str) -> dict[str, Any]:
    start = _parse_dt(start_iso)
    end = _parse_dt(end_iso) if end_iso else start + timedelta(hours=2)
    try:
        creds = _build_credentials(conn)
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        cal_id = conn.get("calendar_id") or "primary"
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start.isoformat() + "Z", "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat() + "Z", "timeZone": "UTC"},
        }
        created = service.events().insert(calendarId=cal_id, body=body).execute()
        return {
            "ok": True,
            "event_id": created.get("id"),
            "start": start.isoformat() + "Z",
            "end": end.isoformat() + "Z",
        }
    except Exception as exc:
        logger.exception("Calendar create failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def create_event_for_profile(
    profile_id: str,
    *,
    summary: str,
    start_iso: str | None,
    end_iso: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    conn = _get_connection_for_profile(profile_id)
    if not conn:
        return {"ok": False, "error": "not_connected", "profile_id": profile_id}
    out = _create_event(conn, summary=summary, start_iso=start_iso, end_iso=end_iso, description=description)
    out["profile_id"] = profile_id
    return out


def create_event_for_vendor(
    vendor_id: str,
    *,
    summary: str,
    start_iso: str | None,
    end_iso: str | None = None,
    description: str = "",
) -> dict[str, Any]:
    conn = _get_connection_for_vendor(vendor_id)
    if not conn:
        return {"ok": False, "error": "not_connected", "vendor_id": vendor_id}
    out = _create_event(conn, summary=summary, start_iso=start_iso, end_iso=end_iso, description=description)
    out["vendor_id"] = vendor_id
    return out


def book_maintenance_on_both_calendars(
    *,
    tenant_profile_id: str | None,
    vendor_id: str | None,
    summary: str,
    scheduled_iso: str | None,
    request_id: str,
) -> dict[str, Any]:
    desc = f"EstateFlow maintenance (request {request_id})"
    start = _parse_dt(scheduled_iso)
    end = (start + timedelta(hours=2)).isoformat() + "Z"
    start_s = start.isoformat() + "Z"

    tenant_result = None
    vendor_result = None
    if tenant_profile_id:
        tenant_result = create_event_for_profile(
            tenant_profile_id, summary=summary, start_iso=start_s, end_iso=end, description=desc
        )
    if vendor_id:
        vendor_result = create_event_for_vendor(
            vendor_id, summary=summary, start_iso=start_s, end_iso=end, description=desc
        )

    return {
        "start": start_s,
        "end": end,
        "tenant": tenant_result,
        "vendor": vendor_result,
        "tenant_event_id": (tenant_result or {}).get("event_id"),
        "vendor_event_id": (vendor_result or {}).get("event_id"),
    }