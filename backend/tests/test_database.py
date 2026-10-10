"""Against a real Postgres with pgvector: the schema's own guarantees, which mocks cannot show.

Skipped unless TEST_DATABASE_URL names a throwaway database with every migration applied (CI's
`database` job does this). Never point it at a shared database: these tests write rows.
"""

import asyncio
import os
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app import audit_routes, quiet_hours, scheduled_sends, template_store, todo
from app.audit import AuditAction, audit_row
from app.core.constants import EMBEDDING_DIM
from app.core.cursor import decode_cursor
from app.core.ownership import Scope
from app.core.ratelimit import PostgresCounters
from app.dashboard import list_dashboard_emails, snooze_email
from app.db.migrate import apply_pending, pending
from app.db.models import (
    AuthStatus,
    Chunk,
    DocType,
    Document,
    Embedding,
    MaskingStatus,
    Message,
    SentMessage,
    UserProfile,
)
from app.db.session import get_engine, get_sessionmaker
from app.jobs import claim_requested, request_draft
from app.ml.categorise import classify_pending
from app.quiet_hours import QuietHoursView
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


def test_templates_save_list_by_use_update_and_delete_for_their_owner():
    owner = uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        first = await template_store.create_template(owner, {"title": "A", "body": "Hi {{name}}", "language": "en",
                                                             "trigger_keywords": ["invoice"]})
        second = await template_store.create_template(owner, {"title": "B", "body": "Hai", "language": "ms",
                                                              "trigger_keywords": []})
        await template_store.mark_used(second.id)
        order = [t.title for t in await template_store.list_templates(owner)]
        updated = await template_store.update_template(owner, first.id, {"title": "A2", "body": "x",
                                                                         "language": "en", "trigger_keywords": []})
        someone_else = await template_store.update_template(uuid4(), first.id, {"title": "no"})
        deleted = await template_store.delete_template(owner, first.id)
        left = [t.title for t in await template_store.list_templates(owner)]
        return first.created_at, order, updated.title, someone_else, deleted, left

    created_at, order, title, someone_else, deleted, left = _run(scenario())
    assert created_at is not None and order == ["B", "A"] and title == "A2"
    assert someone_else is None and deleted and left == ["B"]


def test_quiet_hours_keep_one_company_row_and_one_per_user():
    owner = uuid4()
    view = QuietHoursView(start=time(22), end=time(7), weekendDays=[5, 6], timezone="Asia/Kuala_Lumpur")

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        await quiet_hours.save(None, view)
        await quiet_hours.save(None, view)  # the company row is updated, not duplicated
        await quiet_hours.save(owner, view.model_copy(update={"weekendDays": [6, 7]}))
        mine = await quiet_hours.settings_for(owner)
        await quiet_hours.follow_company(owner)
        back = await quiet_hours.settings_for(owner)
        companies = await _scalar("SELECT count(*) FROM quiet_hours WHERE user_id IS NULL")
        return mine, back, companies

    mine, back, companies = _run(scenario())
    assert companies == 1 and mine.effective.weekendDays == [6, 7] and mine.company.weekendDays == [5, 6]
    assert back.personal is None and back.effective == back.company


def test_a_reschedule_replaces_the_waiting_send_and_a_cancel_shows_its_reason():
    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            message = Message(id=uuid4(), gmail_message_id=f"sched-{uuid4()}", masking_status=MaskingStatus.COMPLETE)
            session.add(message)
        first = datetime(2030, 1, 1, 1, tzinfo=timezone.utc)
        await scheduled_sends.hold(message.id, None, "one", first)
        await scheduled_sends.hold(message.id, None, "two", first + timedelta(hours=1))
        rows = await _scalar(f"SELECT count(*) FROM scheduled_send WHERE message_id = '{message.id}'")
        waiting = (await scheduled_sends.states_for([message.id]))[message.id]
        await scheduled_sends.cancel_pending(message.id, scheduled_sends.CancelReason.THEY_REPLIED)
        after = (await scheduled_sends.states_for([message.id]))[message.id]
        return rows, waiting, after

    rows, waiting, after = _run(scenario())
    assert rows == 1 and waiting.send_at == datetime(2030, 1, 1, 2, tzinfo=timezone.utc)
    assert after.send_at is None and after.cancelled == scheduled_sends.CancelReason.THEY_REPLIED


def test_a_snoozed_email_leaves_the_inbox_until_it_is_due_and_comes_back_unread():
    owner = uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            message = Message(id=uuid4(), user_id=owner, gmail_message_id=f"snz-{uuid4()}", subject="s",
                              masking_status=MaskingStatus.COMPLETE, read_at=datetime.now(timezone.utc))
            session.add(message)
        scope = Scope(owner_id=owner)
        snoozed = await snooze_email(str(message.id), datetime.now(timezone.utc) + timedelta(hours=3), scope=scope)
        hidden = [e.id for e in (await list_dashboard_emails(scope, "", 10, None)).emails]
        await snooze_email(str(message.id), None, scope=scope)
        shown = (await list_dashboard_emails(scope, "", 10, None)).emails
        return str(message.id), snoozed, hidden, shown

    pk, snoozed, hidden, shown = _run(scenario())
    assert snoozed.snoozedUntil is not None and not snoozed.isRead and pk not in hidden
    assert [e.id for e in shown] == [pk] and not shown[0].isRead


def test_a_snoozed_email_with_a_reply_waiting_stays_reachable_to_cancel_it():
    owner = uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            message = Message(id=uuid4(), user_id=owner, gmail_message_id=f"sw-{uuid4()}", subject="s",
                              masking_status=MaskingStatus.COMPLETE,
                              snoozed_until=datetime.now(timezone.utc) + timedelta(days=2))
            session.add(message)
        await scheduled_sends.hold(message.id, owner, "Thanks.", datetime.now(timezone.utc) + timedelta(days=1))
        listed = (await list_dashboard_emails(Scope(owner_id=owner), "", 10, None)).emails
        return str(message.id), listed

    pk, listed = _run(scenario())
    assert [e.id for e in listed] == [pk] and listed[0].scheduledFor is not None


def test_the_todo_lists_what_needs_the_reader_and_what_is_still_waiting():
    owner = uuid4()
    now = datetime.now(timezone.utc)

    def message(**fields) -> Message:
        return Message(**({"id": uuid4(), "user_id": owner, "gmail_message_id": f"td-{uuid4()}", "subject": "s",
                           "masking_status": MaskingStatus.COMPLETE, "auth_status": AuthStatus.PASS} | fields))

    def sent(thread: str, days_ago: int, body: str) -> SentMessage:
        return SentMessage(user_id=owner, gmail_id=f"g-{uuid4()}", thread_id=thread,
                           sent_at=now - timedelta(days=days_ago), body_masked=body)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        acting = message(action_items=["Pay the invoice"])
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([
                acting,
                message(needs_human_review=True, draft_reply="Hi"),
                message(draft_reply="Hi", generated_at=now - timedelta(days=2)),
                message(action_items=["x"], auth_status=AuthStatus.SPOOF_DETECTED),
                message(action_items=["x"], dismissed_at=now),
                message(thread_id="B", created_at=now - timedelta(days=1)),  # their answer in thread B
            ])
        async with get_sessionmaker()() as session, session.begin():
            waiting = sent("A", 8, "Could you confirm the date?")
            session.add_all([waiting, sent("A", 12, "Older send in the same thread?"),
                             sent("B", 8, "Can you send the PO?"), sent("C", 8, "Thanks, received!"),
                             sent("D", 0, "Could you call me?")])
        scope = Scope(owner_id=owner)
        before = await todo.todo_for(scope, f"{owner}@example.com")
        await todo.dismiss_waiting(scope, waiting.id)
        await todo.dismiss_email(scope, acting.id, is_dismissed=True)
        assert not await todo.dismiss_email(Scope(owner_id=uuid4()), acting.id, is_dismissed=True)
        after = await todo.todo_for(scope, f"{owner}@example.com")
        return before, after

    before, after = _run(scenario())
    assert (before.needsAction.total, before.needsReview.total, before.unsentDrafts.total) == (1, 1, 1)
    assert [w.threadId for w in before.waiting] == ["A"] and before.waiting[0].workingDays >= 3
    assert before.count == 1 + 1 + 1 + 1
    assert after.needsAction.total == 0 and after.waiting == []
