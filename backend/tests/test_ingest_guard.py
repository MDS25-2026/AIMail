import asyncio

from app.core.ownership import EVERYTHING
from app.rag.ingest import ingest_text


def test_ingest_text_returns_zero_for_empty_input_without_touching_the_db():
    # No chunks -> returns before opening a session, so this runs with no database.
    assert asyncio.run(ingest_text("paste://x", "x", "   ", scope=EVERYTHING)) == 0


def test_sentences_split_the_same_and_stay_fast_on_long_runs_of_whitespace():
    import time

    from app.rag.chunk import _sentences

    assert _sentences("First one.   Second\n\tone! Third? fourth stays.") == [
        "First one.", "Second one!", "Third? fourth stays."]
    started = time.perf_counter()
    _sentences("a." + " " * 200_000 + "x" + ". " * 50_000 + "Y")
    assert time.perf_counter() - started < 1.0
