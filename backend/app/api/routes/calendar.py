import secrets
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from app.auth import get_current_user
from app.config import get_settings
from app.db import get_supabase_admin
from app.services.calendar_service import calendar_connected_for_user
from app.services.calendar_tokens import encrypt_token

router = APIRouter(prefix="/calendar", tags=["calendar"])

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def _oauth_flow() -> Flow:
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth not configured. Set GOOGLE_OAUTH_CLIENT_ID and SECRET.",
        )
    client_config = {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
    )


def _oauth_state(user: dict) -> str:
    if user.get("auth_type") == "vendor":
        return f"vendor:{user['vendor_id']}:{secrets.token_urlsafe(16)}"
    return f"profile:{user['id']}:{secrets.token_urlsafe(16)}"


@router.get("/status")
async def calendar_status(user: dict = Depends(get_current_user)):
    return {
        "data": {
            "connected": calendar_connected_for_user(user),
            "account_id": user.get("vendor_id") if user.get("auth_type") == "vendor" else user["id"],
        }
    }


@router.get("/connect")
async def calendar_connect(user: dict = Depends(get_current_user)):
    flow = _oauth_flow()
    state = _oauth_state(user)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return {"data": {"auth_url": auth_url, "state": state}}


@router.get("/callback")
async def calendar_callback(
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
):
    settings = get_settings()
    frontend = settings.cors_origins.split(",")[0].strip()

    if error or not code or not state:
        return RedirectResponse(f"{frontend}/login?calendar_error=1")

    parts = state.split(":")
    if len(parts) < 2 or parts[0] not in ("profile", "vendor"):
        return RedirectResponse(f"{frontend}/login?calendar_error=1")

    owner_type, owner_id = parts[0], parts[1]
    flow = _oauth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials
    expiry = creds.expiry.isoformat() if creds.expiry else None

    admin = get_supabase_admin()
    row: dict = {
        "provider": "google",
        "calendar_id": "primary",
        "access_token_enc": encrypt_token(creds.token or ""),
        "refresh_token_enc": encrypt_token(creds.refresh_token or "") if creds.refresh_token else None,
        "token_expiry": expiry,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if owner_type == "vendor":
        row["vendor_id"] = owner_id
        row["profile_id"] = None
        existing = (
            admin.table("calendar_connections").select("id").eq("vendor_id", owner_id).execute()
        )
        if existing.data:
            admin.table("calendar_connections").update(row).eq("vendor_id", owner_id).execute()
        else:
            admin.table("calendar_connections").insert(row).execute()
        dest = "/vendor/calendar"
    else:
        row["profile_id"] = owner_id
        existing = (
            admin.table("calendar_connections").select("id").eq("profile_id", owner_id).execute()
        )
        if existing.data:
            admin.table("calendar_connections").update(row).eq("profile_id", owner_id).execute()
        else:
            admin.table("calendar_connections").insert(row).execute()
        dest = "/calendar"

    return RedirectResponse(f"{frontend}{dest}?connected=1")


@router.delete("/disconnect")
async def calendar_disconnect(user: dict = Depends(get_current_user)):
    admin = get_supabase_admin()
    if user.get("auth_type") == "vendor":
        admin.table("calendar_connections").delete().eq("vendor_id", user["vendor_id"]).execute()
    else:
        admin.table("calendar_connections").delete().eq("profile_id", user["id"]).execute()
    return {"ok": True}
