from app.core.config import Settings


def test_async_url_injects_asyncpg_driver():
    settings = Settings(database_url="postgresql://u:p@h:5432/db", google_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_async_url_normalizes_legacy_postgres_scheme():
    settings = Settings(database_url="postgres://u:p@h/db", google_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h/db"


def test_async_url_is_idempotent_when_driver_already_present():
    settings = Settings(database_url="postgresql+asyncpg://u:p@h/db", google_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h/db"


def test_a_deployed_environment_refuses_to_start_without_its_secrets(monkeypatch):
    import pytest

    from app.core.config import MisconfiguredError, Settings

    monkeypatch.setenv("ENVIRONMENT", "prod")
    with pytest.raises(MisconfiguredError, match="agent_token"):
        Settings(_env_file=None)


def test_a_deployed_environment_accepts_a_keyring_for_either_key(monkeypatch):
    from app.core.config import Settings

    for name, value in {"ENVIRONMENT": "prod", "GOOGLE_API_KEY": "k", "BACKEND_API_TOKEN": "t",
                        "AGENT_TOKEN": "a", "FRONTEND_ORIGINS": "https://app.example",
                        "TOKEN_ENCRYPTION_KEYS": "k1:x", "PII_VAULT_KEYS": "k1:y",
                        "BACKEND_PUBLIC_URL": "https://api.example", "DASHBOARD_URL": "https://app.example"}.items():
        monkeypatch.setenv(name, value)
    assert Settings(_env_file=None).environment == "prod"


def test_a_deployed_environment_refuses_a_localhost_public_url(monkeypatch):
    import pytest

    from app.core.config import MisconfiguredError, Settings

    for name, value in {"ENVIRONMENT": "staging", "GOOGLE_API_KEY": "k", "BACKEND_API_TOKEN": "t",
                        "AGENT_TOKEN": "a", "FRONTEND_ORIGINS": "https://app.example",
                        "TOKEN_ENCRYPTION_KEY": "x", "PII_VAULT_KEY": "y"}.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(MisconfiguredError, match="backend_public_url"):
        Settings(_env_file=None)
