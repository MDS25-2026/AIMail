"""Testing GET /documents/{document_id} for Knowledge Base document preview."""

from uuid import uuid4

from app import main
from app.rag.library import DocumentDetail
from tests.conftest import AUTH_HEADERS


def test_get_document_success(api_client, monkeypatch):
    doc_id = uuid4()
    mock_detail: DocumentDetail = {
        "document_id": doc_id,
        "title": "Refund Policy",
        "source": "paste://Refund Policy",
        "doc_type": "text",
        "chunk_count": 2,
        "content": "Section 1: Returns\n\nSection 2: Refunds",
        "chunks": [
            {"id": uuid4(), "chunk_idx": 0, "section": "Returns", "content": "Section 1: Returns"},
            {"id": uuid4(), "chunk_idx": 1, "section": "Refunds", "content": "Section 2: Refunds"},
        ],
    }

    async def mock_get(d_id, _scope):
        if d_id == doc_id:
            return mock_detail
        return None

    monkeypatch.setattr(main, "get_document_detail", mock_get)

    res = api_client.get(f"/documents/{doc_id}", headers=AUTH_HEADERS)
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Refund Policy"
    assert data["chunk_count"] == 2
    assert "Section 1: Returns" in data["content"]
    assert len(data["chunks"]) == 2


def test_get_document_not_found(api_client, monkeypatch):
    async def mock_get(_d_id, _scope):
        return None

    monkeypatch.setattr(main, "get_document_detail", mock_get)

    res = api_client.get(f"/documents/{uuid4()}", headers=AUTH_HEADERS)
    assert res.status_code == 404


def test_get_document_invalid_uuid(api_client):
    res = api_client.get("/documents/invalid-uuid", headers=AUTH_HEADERS)
    assert res.status_code == 422
