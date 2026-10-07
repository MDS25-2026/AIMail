"""Removing a document from the knowledge base (specs/features/rag-retrieval.md)."""

import asyncio
from uuid import uuid4

from app import main
from app.core.ownership import Scope
from app.rag import library
from tests.conftest import AUTH_HEADERS


def _fake_delete(monkeypatch, found: bool) -> list:
    asked = []

    async def delete(document_id, scope):
        asked.append(document_id)
        return found

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(main, "delete_document", delete)
    monkeypatch.setattr(main, "audit", nothing)
    return asked


def test_removing_a_document_returns_no_content(api_client, monkeypatch):
    document_id = uuid4()
    asked = _fake_delete(monkeypatch, found=True)
    response = api_client.delete(f"/documents/{document_id}", headers=AUTH_HEADERS)
    assert response.status_code == 204 and asked == [document_id]


def test_a_document_outside_the_users_library_looks_missing(api_client, monkeypatch):
    _fake_delete(monkeypatch, found=False)
    assert api_client.delete(f"/documents/{uuid4()}", headers=AUTH_HEADERS).status_code == 404


def test_a_malformed_id_is_refused_before_any_delete(api_client, monkeypatch):
    asked = _fake_delete(monkeypatch, found=True)
    assert api_client.delete("/documents/not-a-uuid", headers=AUTH_HEADERS).status_code == 422
    assert asked == []


def test_only_the_owners_library_document_can_be_deleted_never_a_past_reply(monkeypatch):
    statements = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return self

        async def scalar(self, statement):
            statements.append(str(statement.compile(compile_kwargs={"literal_binds": True})))

    monkeypatch.setattr(library, "get_sessionmaker", lambda: _Session)
    owner = uuid4()
    assert asyncio.run(library.delete_document(uuid4(), Scope(owner_id=owner))) is False
    assert f"document.user_id = '{owner.hex}'" in statements[0]
    assert "doc_type IS DISTINCT FROM 'sent_reply'" in statements[0]
