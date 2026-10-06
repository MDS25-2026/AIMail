from uuid import uuid4

from app.rag.utils import format_rag_context


def _chunk(title: str, content: str):
    return {"chunk_id": uuid4(), "content": content, "similarity_score": 0.9, "source_title": title}


def test_formats_each_chunk_with_its_source_title():
    out = format_rag_context(
        [_chunk("Code of Conduct", "Gifts are limited."), _chunk("Code of Conduct", "Report conflicts.")]
    )
    assert "[Code of Conduct] Gifts are limited." in out
    assert "[Code of Conduct] Report conflicts." in out
    assert out.count("\n\n") == 1  # one blank-line separator between the two chunks


def test_empty_chunks_yields_empty_string():
    assert format_rag_context([]) == ""
