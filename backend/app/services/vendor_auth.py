"""JWT sessions for vendors (vendors table auth, separate from Supabase)."""

from datetime import datetime, timedelta
from typing import Any

import jwt

from app.config import get_settings


def _secret() -> str:
    settings = get_settings()
    secret = settings.vendor_jwt_secret or settings.supabase_jwt_secret
    if not secret:
        raise RuntimeError("Set VENDOR_JWT_SECRET or SUPABASE_JWT_SECRET for vendor sessions")
    return secret


def create_vendor_access_token(*, vendor_id: str, email: str) -> str:
    settings = get_settings()
    exp = datetime.utcnow() + timedelta(hours=settings.vendor_jwt_expire_hours)
    payload = {
        "sub": vendor_id,
        "email": email,
        "role": "vendor",
        "typ": "vendor",
        "exp": exp,
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def decode_vendor_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if payload.get("typ") != "vendor" or payload.get("role") != "vendor":
        return None
    return payload
