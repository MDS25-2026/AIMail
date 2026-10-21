"""Loading an email never pulls its search columns: the vector alone outweighs the rest of the row."""

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import Message


def _loaded_columns() -> str:
    return str(select(Message).compile(dialect=postgresql.dialect()))


def test_an_email_loads_without_its_embedding_or_search_vector():
    loaded = _loaded_columns()
    assert "messages.embedding" not in loaded and "messages.search_vector" not in loaded


def test_an_email_still_loads_its_body():
    assert "messages.body_masked" in _loaded_columns()
