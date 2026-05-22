"""Encrypt/decrypt OAuth tokens at rest (Fernet)."""

import base64
import logging
from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet | None:
    key = get_settings().calendar_token_encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        logger.warning("Invalid CALENDAR_TOKEN_ENCRYPTION_KEY — generate with Fernet.generate_key()")
        return None


def encrypt_token(plain: str) -> str:
    f = _fernet()
    if not f:
        return plain
    return f.encrypt(plain.encode()).decode()


def decrypt_token(cipher: str) -> str:
    f = _fernet()
    if not f:
        return cipher
    try:
        return f.decrypt(cipher.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt calendar token")
        raise


def connection_row_to_credentials(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "access_token": decrypt_token(row["access_token_enc"]),
        "refresh_token": decrypt_token(row["refresh_token_enc"]) if row.get("refresh_token_enc") else None,
        "token_expiry": row.get("token_expiry"),
        "calendar_id": row.get("calendar_id") or "primary",
    }
