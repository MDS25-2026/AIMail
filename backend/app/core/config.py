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
    # One Google AI key for everything: the backend's embeddings and the agent's drafting.
    google_api_key: str
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
    # Encrypts each email's personal-detail vault (specs/features/restorable-masking.md): 32 random
    # bytes, base64, shared with the listener. Empty means details are never stored or shown.
    pii_vault_key: str = ""
    # A vault is emptied after this many days, or 7 days after its reply was sent.
    vault_retention_days: int = 30
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


@lru_cache
def get_settings() -> Settings:
    # Required fields are supplied by the environment / .env at runtime.
    return Settings()  # type: ignore[call-arg]

