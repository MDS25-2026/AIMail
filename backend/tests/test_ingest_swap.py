"""A re-uploaded document replaces the old copy only once it is embedded (epic #138 line 60)."""

import asyncio
from uuid import uuid4

import pytest

from app.core.ownership import Scope
from app.core.providers import Provider
from app.rag import ingest
from app.rag.chunk import Piece
from app.rag.errors import EmbeddingError

OWNER = uuid4()


@pytest.fixture
def pipeline(monkeypatch):
    state = {"stored": [], "embedded": [], "provider": Provider.GEMINI, "pieces": [Piece("Leave is 14 days.")]}

    async def mask(text, profile):
        return text

    async def provider(_owner):
        return state["provider"]

    async def embed(texts, *, provider, purpose):
        if state.get("fail"):
            raise EmbeddingError("quota")
        state["embedded"].append(len(texts))
        return [[0.0] for _ in texts]

    async def store(source, title, pieces, *, scope, doc_type, vectors=None):
        state["stored"].append(vectors)

    async def nothing():
        return None

    monkeypatch.setattr(ingest, "mask_document", mask)
    monkeypatch.setattr(ingest, "chunk_sections", lambda _text: state["pieces"])
    monkeypatch.setattr(ingest, "provider_for", provider)
    monkeypatch.setattr(ingest.model_gateway, "embed_documents", embed)
    monkeypatch.setattr(ingest, "store_chunks", store)
    monkeypatch.setattr(ingest, "embed_pending_locally_logged", nothing)
    return state


def _ingest():
    return asyncio.run(ingest.ingest_text("upload://leave.pdf", "Leave", "Leave is 14 days.",
                                          scope=Scope(owner_id=OWNER)))


def test_a_failed_embedding_leaves_the_earlier_copy_in_place(pipeline):
    pipeline["fail"] = True
    with pytest.raises(EmbeddingError):
        _ingest()
    assert pipeline["stored"] == []


def test_the_new_copy_goes_in_with_its_vectors(pipeline):
    assert _ingest() == 1
    assert pipeline["stored"] == [[[0.0]]]


def test_a_private_mode_owners_document_is_not_sent_to_gemini(pipeline):
    pipeline["provider"] = Provider.LOCAL
    _ingest()
    assert pipeline["embedded"] == [] and pipeline["stored"] == [None]


def test_a_long_document_is_embedded_in_batches(pipeline):
    pipeline["pieces"] = [Piece(f"Clause {i}.") for i in range(ingest.EMBED_BATCH + 5)]
    _ingest()
    assert pipeline["embedded"] == [ingest.EMBED_BATCH, 5]
