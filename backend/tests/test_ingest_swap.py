"""A re-uploaded document replaces the old copy only once it is embedded (epic #138 line 60)."""

import asyncio
from uuid import uuid4

import pytest

import model_gateway
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


@pytest.fixture
def receipts(pipeline, monkeypatch):
    saved = []

    async def embed(texts, *, provider, purpose):
        tracking = model_gateway._egress.get()
        if tracking is not None:
            tracking.append(model_gateway.Egress(purpose=purpose, provider=provider, chars=1, sha256="x",
                                                 hidden={}, caught=0))
        if pipeline.get("fail"):
            raise EmbeddingError("quota")
        return [[0.0] for _ in texts]

    async def save(records, *, user_id, message_id):
        saved.append((len(records), user_id, message_id))

    monkeypatch.setattr(ingest.model_gateway, "embed_documents", embed)
    monkeypatch.setattr(ingest, "save_egress", save)
    return saved


def test_indexing_a_document_is_on_its_owners_privacy_receipt(receipts):
    _ingest()
    assert receipts == [(1, OWNER, None)]


def test_a_failed_indexing_still_records_what_was_sent(pipeline, receipts):
    pipeline["fail"] = True
    with pytest.raises(EmbeddingError):
        _ingest()
    assert receipts == [(1, OWNER, None)]


def test_embed_pending_isolates_rejected_chunk(monkeypatch):
    from app.core.constants import EMBEDDING_DIM
    from app.db.models import Chunk

    chunk1 = Chunk(id=uuid4(), document_id=uuid4(), chunk_idx=0, content="good chunk")
    chunk2 = Chunk(id=uuid4(), document_id=uuid4(), chunk_idx=1, content="bad chunk")

    class _Scalars:
        def __init__(self, items):
            self.items = items

        def all(self):
            res = self.items
            self.items = []
            return res

    added = []
    calls = {"count": 0}

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return self

        async def scalars(self, _stmt):
            calls["count"] += 1
            return _Scalars([chunk1, chunk2] if calls["count"] == 1 else [])

        def add(self, entity):
            added.append(entity)

        def add_all(self, entities):
            added.extend(entities)

    async def mock_embed(texts, *, provider, purpose):
        if len(texts) > 1:
            raise EmbeddingError("batch failed because of bad chunk")
        if texts[0] == "bad chunk":
            raise EmbeddingError("safety policy violation")
        return [[0.1] * EMBEDDING_DIM]

    monkeypatch.setattr(ingest.model_gateway, "embed_documents", mock_embed)
    monkeypatch.setattr(ingest, "get_sessionmaker", lambda: lambda: _FakeSession())

    embedded_count = asyncio.run(ingest.embed_pending(batch_size=10))
    assert embedded_count == 1
    assert len(added) == 2
    assert added[0].chunk_id == chunk1.id and added[0].embedding == [0.1] * EMBEDDING_DIM
    assert added[1].chunk_id == chunk2.id and added[1].embedding == [0.0] * EMBEDDING_DIM
