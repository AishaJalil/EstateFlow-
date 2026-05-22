from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent


def _discover_env_files() -> tuple[str, ...]:
    """Load backend/.env first, then repo-root .env (where keys are often placed)."""
    candidates = [_BACKEND_DIR / ".env", _PROJECT_ROOT / ".env"]
    found = [str(p) for p in candidates if p.is_file()]
    return tuple(found) if found else (str(_BACKEND_DIR / ".env"),)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_discover_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str = ""

    openrouter_api_key: str
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_timeout_seconds: int = 30
    # Priority uses risk matrix + rules by default (fast). Set true to add a second LLM call.
    priority_use_llm: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    use_ollama_fallback: bool = False

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    vendor_search_radius_km: float = 25.0
    brave_api_key: str = ""
    enable_external_vendor_search: bool = False

    # WhatsApp via TextMeBot
    textmebot_api_key: str = ""
    textmebot_sender_phone: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
