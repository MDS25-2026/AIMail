import asyncio

from app.rag.ingest import ingest_text


def test_ingest_text_returns_zero_for_empty_input_without_touching_the_db():
    # No chunks -> returns before opening a session, so this runs with no database.
    assert asyncio.run(ingest_text("paste://x", "x", "   ")) == 0
