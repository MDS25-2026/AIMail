"""Configuration for the backend and the agent: the only code that reads the environment.

Values come from the process environment, then the repo-root .env. AIMAIL_ENV_FILE names another file, and
an empty value reads none (tests do this, so a developer's .env never changes a test's outcome).
"""

import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    CHAT_MODEL,
    DEFAULT_ADMIN_ORIGINS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE_VARIABLE = "AIMAIL_ENV_FILE"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class Environment(StrEnum):
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class MisconfiguredError(RuntimeError):
    """Raised at startup when a deployed environment is missing a setting it cannot run safely without."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    environment: Environment = Environment.DEV
    # Needed by the backend and scripts, not the agent; checked where the engine is created.
    database_url: str = ""
    # One Google AI key for everything: the backend's embeddings and the agent's drafting.
    google_api_key: str = ""
    # The agent (:8001) accepts only requests carrying this; empty means loopback-only dev use.
    agent_token: str = ""
    # Dashboard origins allowed to call the API with the session cookie, comma-separated.
    frontend_origins: str = ""
    admin_origins: str = DEFAULT_ADMIN_ORIGINS
    # Proxies in front of the API that append to X-Forwarded-For; 0 trusts only the socket address.
    trusted_proxy_hops: int = 0
    log_level: str = "INFO"
    # "json" in a deployed environment so the host's log search can filter by field.
    log_format: str = "text"
    # How to read 03/04/2026 in an email: DMY (Malaysia), MDY or YMD.
    date_order: str = ""
    # The agent's whole-request budget and its Gemini models.
    agent_deadline_seconds: float = 0.0
    gemini_agent_model: str = ""
    gemini_fallback_model: str = ""
    gemini_base_url: str = ""
    # Shared bearer token every API caller must present (see app/core/auth.py). Empty means
    # the API refuses all requests rather than silently running unauthenticated.
    backend_api_token: str = ""
    embedding_model: str = EMBEDDING_MODEL
    embedding_dim: int = EMBEDDING_DIM
    gemini_chat_model: str = CHAT_MODEL
    email_agent_url: str = "http://127.0.0.1:8001"  # Lane C /process-email service
    # Dashboard sign-in (docs/adr/0005): Supabase sends the user back to BACKEND_PUBLIC_URL, which
    # sends them on to DASHBOARD_URL once the session cookies are set.
    backend_public_url: str = "http://localhost:8000"
    # Encrypts stored Google refresh tokens (app/core/token_crypt.py): 32 random bytes, base64.
    # Empty means no token can be stored or read (fail closed). Shared with the listener.
    token_encryption_key: str = ""
    # Key rotation (app/core/sealed_box.py): "kid:base64key,kid2:base64key", first entry primary.
    # TOKEN_ENCRYPTION_KEY above stays readable as kid "legacy". Shared with the listener.
    token_encryption_keys: str = ""
    # Encrypts each email's personal-detail vault (specs/features/restorable-masking.md): 32 random
    # bytes, base64, shared with the listener. Empty means details are never stored or shown.
    pii_vault_key: str = ""
    # The vault keyring, in the same form as TOKEN_ENCRYPTION_KEYS; PII_VAULT_KEY is its "legacy" kid.
    pii_vault_keys: str = ""
    # A vault is emptied after this many days, or 7 days after its reply was sent.
    vault_retention_days: int = 30
    # Readable message content (body, summary, draft) is cleared after this many days; 0 keeps it (app/retention.py).
    message_content_retention_days: int = 0
    # The Google OAuth client in Supabase's Google provider; refreshes connected users' tokens.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    dashboard_url: str = "http://localhost:8090"
    # Masks uploaded documents before storage (app/rag/mask.py); shared with the listener and agent.
    presidio_analyzer_url: str = "http://localhost:5001/analyze"
    # Private mode (specs/features/local-model.md): the company's local model; "" = not offered.
    local_llm_model: str = ""
    local_llm_url: str = "http://localhost:11434"
    # Private mode's search: a local embedding model on the same Ollama; "" = no search in Private mode.
    local_embedding_model: str = ""
    # Reuse the listener's OAuth creds (gmail.send scope) to send approved replies. Best-practice
    # upgrade: a service account + domain-wide delegation so the backend has its own credentials.
    gmail_credentials_path: str = str(_REPO_ROOT / "listener" / "credentials.json")
    gmail_token_path: str = str(_REPO_ROOT / "listener" / "token.json")
    # Fallback for the owner of the original token.json mailbox's unowned rows, if Gmail cannot be
    # asked at startup (app/core/mailbox.py). Connected users never need it.
    mailbox_owner_email: str = ""
    auto_generate: bool = True  # background poller pre-generates drafts so opens are instant
    generate_poll_seconds: int = 60
    priority_model: str = "baseline"  # "baseline" (TF-IDF) or "distilbert" — which classifier backfill uses
    # Admin console (docs/adr/0004). SUPABASE_URL is shared with the listener; the anon key is the
    # project's publishable key, used server-side for the password grant. Empty means admin sign-in
    # is refused (fail closed). The service key is read only by scripts/admin_accounts.py.
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    # Secure cookies need HTTPS, except on localhost, which browsers treat as secure. Turn off only
    # to reach the backend over plain HTTP by LAN address.
    admin_cookie_secure: bool = True

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


    @model_validator(mode="after")
    def _deployed_settings_are_safe(self) -> "Settings":
        if self.environment == Environment.DEV:
            return self
        missing = [" or ".join(names) for names in _REQUIRED_WHEN_DEPLOYED
                   if not any(getattr(self, name) for name in names)]
        local = [name for name in _PUBLIC_URLS if urlparse(getattr(self, name)).hostname in LOCAL_HOSTS]
        if missing or local:
            raise MisconfiguredError(f"{self.environment} needs: {', '.join(missing)}; "
                                     f"public URLs still on localhost: {', '.join(local)}")
        return self


# A deployed instance without these would run unauthenticated, unencrypted or unreachable.
# Each entry is satisfied by any one of its settings (a single key or its keyring).
_REQUIRED_WHEN_DEPLOYED: tuple[tuple[str, ...], ...] = (
    ("google_api_key",), ("backend_api_token",), ("agent_token",), ("frontend_origins",),
    ("token_encryption_key", "token_encryption_keys"), ("pii_vault_key", "pii_vault_keys"),
)
_PUBLIC_URLS = ("backend_public_url", "dashboard_url")


def _env_file() -> Path | None:
    chosen = os.environ.get(ENV_FILE_VARIABLE)
    if chosen is None:
        return _REPO_ROOT / ".env"
    return Path(chosen) if chosen else None


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=_env_file())

