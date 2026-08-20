"""Backend configuration, loaded from environment / repo-root .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import CHAT_MODEL, EMBEDDING_DIM, EMBEDDING_MODEL

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env", extra="ignore", case_sensitive=False
    )

    database_url: str
    gemini_api_key: str
    embedding_model: str = EMBEDDING_MODEL
    embedding_dim: int = EMBEDDING_DIM
    gemini_chat_model: str = CHAT_MODEL
    email_agent_url: str = "http://localhost:8001"  # Lane C /process-email service
    # Reuse the listener's OAuth creds (gmail.send scope) to send approved replies. Best-practice
    # upgrade: a service account + domain-wide delegation so the backend has its own credentials.
    gmail_credentials_path: str = str(_REPO_ROOT / "listener" / "credentials.json")
    gmail_token_path: str = str(_REPO_ROOT / "listener" / "token.json")
    auto_generate: bool = True  # background poller pre-generates drafts so opens are instant
    generate_poll_seconds: int = 60
    priority_model: str = "baseline"  # "baseline" (TF-IDF) or "distilbert" — which classifier backfill uses

    @property
    def async_database_url(self) -> str:
        """DATABASE_URL with the asyncpg driver injected.

        Lets you paste the plain postgresql:// URL Supabase shows (and psql uses);
        SQLAlchemy's async engine needs the +asyncpg driver, so add it here not in .env.
        """
        url = self.database_url
        if "+asyncpg" in url:
            return url
        return url.replace("postgres://", "postgresql://", 1).replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )


@lru_cache
def get_settings() -> Settings:
    # Required fields are supplied by the environment / .env at runtime.
    return Settings()  # type: ignore[call-arg]
