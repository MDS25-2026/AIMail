from app.core.config import Settings


def test_async_url_injects_asyncpg_driver():
    settings = Settings(database_url="postgresql://u:p@h:5432/db", gemini_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h:5432/db"


def test_async_url_normalizes_legacy_postgres_scheme():
    settings = Settings(database_url="postgres://u:p@h/db", gemini_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h/db"


def test_async_url_is_idempotent_when_driver_already_present():
    settings = Settings(database_url="postgresql+asyncpg://u:p@h/db", gemini_api_key="x")
    assert settings.async_database_url == "postgresql+asyncpg://u:p@h/db"
