"""Against a real Postgres with pgvector: the schema's own guarantees, which mocks cannot show.

Skipped unless TEST_DATABASE_URL names a throwaway database with every migration applied (CI's
`database` job does this). Never point it at a shared database: these tests write rows.
"""

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import audit_routes
from app.audit import AuditAction, audit_row
from app.core.constants import EMBEDDING_DIM
from app.core.cursor import decode_cursor
from app.core.ownership import Scope
from app.core.ratelimit import PostgresCounters
from app.dashboard import list_dashboard_emails
from app.db.migrate import apply_pending, pending
from app.db.models import (
    AuthStatus,
    Chunk,
    DocType,
    Document,
    Embedding,
    MaskingStatus,
    Message,
    UserProfile,
)
from app.db.session import get_engine, get_sessionmaker
from app.jobs import claim_requested, request_draft
from app.ml.categorise import classify_pending
from app.rag.chunk import Piece
from app.rag.embedding_models import check_columns
from app.rag.ingest import store_chunks

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to a throwaway database")
CONCURRENT_WRITES = 10


@pytest.fixture(autouse=True)
def database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)


def _run(coroutine):
    async def disposing():
        try:
            return await coroutine
        finally:
            await get_engine().dispose()

    return asyncio.run(disposing())


async def _scalar(sql: str) -> object:
    async with get_sessionmaker()() as session:
        return await session.scalar(text(sql))


def test_migrating_again_changes_nothing():
    assert _run(pending()) == []
    assert _run(apply_pending()) == []


def test_every_public_table_has_row_level_security():
    unprotected = _run(_scalar("""
        SELECT coalesce(string_agg(c.relname, ', '), '') FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"""))
    assert unprotected == ""


async def _write_audit_rows(count: int) -> None:
    async def one() -> None:
        async with get_sessionmaker()() as session, session.begin():
            session.add(audit_row(AuditAction.CONFIRM_SENDER, user_id=uuid4(), message="m"))

    await asyncio.gather(*(one() for _ in range(count)))


def test_concurrent_audit_writes_leave_an_intact_chain():
    async def scenario():
        await _write_audit_rows(CONCURRENT_WRITES)
        async with get_sessionmaker()() as session:
            return (await session.execute(audit_routes._SUMMARY)).one()

    summary = _run(scenario())
    assert summary.is_intact is True and summary.chained >= CONCURRENT_WRITES


@pytest.mark.parametrize("statement", ["UPDATE audit_log SET success = NOT success",
                                       "DELETE FROM audit_log"])
def test_the_audit_log_refuses_to_be_rewritten(statement):
    async def scenario():
        await _write_audit_rows(1)
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(text(statement))

    with pytest.raises(DBAPIError, match="append-only"):
        _run(scenario())


def test_an_edited_row_breaks_the_chain():
    async def scenario():
        await _write_audit_rows(3)
        async with get_engine().connect() as connection:
            transaction = await connection.begin()
            # DDL is transactional in Postgres: the trigger is back once this rolls back.
            await connection.execute(text("ALTER TABLE audit_log DISABLE TRIGGER trg_audit_append_only"))
            await connection.execute(text(
                "UPDATE audit_log SET detail = '{}' WHERE chain_seq = (SELECT min(chain_seq) FROM audit_log)"))
            summary = (await connection.execute(audit_routes._SUMMARY)).one()
            await transaction.rollback()
            return summary

    assert _run(scenario()).is_intact is False


def test_rate_limit_hits_are_counted_once_each_under_concurrency():
    key = f"test:{uuid4()}"

    async def scenario():
        counters = PostgresCounters()
        return await asyncio.gather(*(counters.hit(key, 0.0) for _ in range(CONCURRENT_WRITES)))

    assert sorted(_run(scenario())) == list(range(1, CONCURRENT_WRITES + 1))


def test_the_embedding_columns_have_the_registered_widths():
    _run(check_columns())  # raises MisconfiguredError on a mismatch


def test_an_opened_email_is_queued_once_and_claimed_by_one_worker():
    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            message = Message(id=uuid4(), gmail_message_id=f"test-{uuid4()}", masking_status=MaskingStatus.COMPLETE,
                              auth_status=AuthStatus.PASS)
            session.add(message)
        await request_draft(message.id)
        await request_draft(message.id)  # a second open keeps the first request's place
        first, second = await asyncio.gather(claim_requested(10), claim_requested(10))
        return message.id, first + second

    pk, claimed = _run(scenario())
    assert claimed.count(pk) == 1


def test_paging_the_inbox_shows_every_email_once_even_with_equal_timestamps():
    async def scenario():
        owner = uuid4()
        same_instant = datetime(2026, 10, 8, 9, 0, tzinfo=timezone.utc)
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
            await session.flush()
            session.add_all(Message(id=uuid4(), user_id=owner, created_at=same_instant, subject="s",
                                    gmail_message_id=f"page-{n}")
                            for n in range(5))
        seen, after = [], None
        for _ in range(5):
            page = await list_dashboard_emails(Scope(owner_id=owner), "", 2, after)
            seen += [email.id for email in page.emails]
            if page.nextCursor is None:
                return seen
            after = decode_cursor(page.nextCursor)
        return seen

    seen = _run(scenario())
    assert len(seen) == 5 and len(set(seen)) == 5


def test_the_worker_classifies_an_email_once_and_stores_it():
    async def scenario():
        pk = uuid4()
        async with get_sessionmaker()() as session, session.begin():
            session.add(Message(id=pk, gmail_message_id=f"cat-{pk}", masking_status=MaskingStatus.COMPLETE,
                                subject="Licence renewal", body_masked="Please find the renewal invoice attached."))
        await classify_pending(limit=500)
        async with get_sessionmaker()() as session:
            first = (await session.execute(select(Message.category, Message.category_confidence)
                                           .where(Message.id == pk))).one()
        await classify_pending(limit=500)  # a second pass leaves it alone
        async with get_sessionmaker()() as session:
            second = (await session.execute(select(Message.category).where(Message.id == pk))).scalar_one()
        return first, second

    (stored, confidence), again = _run(scenario())
    assert stored is not None and 0.0 <= confidence <= 1.0 and again == stored


def test_a_re_upload_swaps_in_the_new_chunks_with_their_vectors_in_one_go():
    owner = Scope(owner_id=None)
    source = f"upload://{uuid4()}.pdf"
    vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    async def upload_twice():
        await store_chunks(source, "Leave", [Piece("Old clause.")], scope=owner, doc_type=DocType.POLICY,
                           vectors=[vector])
        await store_chunks(source, "Leave", [Piece("New clause."), Piece("Second clause.")], scope=owner,
                           doc_type=DocType.POLICY, vectors=[vector, vector])
        async with get_sessionmaker()() as session:
            documents = (await session.scalars(select(Document.id).where(Document.source == source))).all()
            contents = (await session.scalars(select(Chunk.content).join(Embedding, Embedding.chunk_id == Chunk.id)
                                              .where(Chunk.document_id.in_(documents)).order_by(Chunk.chunk_idx))).all()
        return documents, contents

    documents, contents = _run(upload_twice())
    assert len(documents) == 1 and contents == ["New clause.", "Second clause."]
