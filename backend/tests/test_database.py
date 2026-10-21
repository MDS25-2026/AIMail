"""Against a real Postgres with pgvector: the schema's own guarantees, which mocks cannot show.

Skipped unless TEST_DATABASE_URL names a throwaway database with every migration applied (CI's
`database` job does this). Never point it at a shared database: these tests write rows.
"""

import asyncio
import json
import os
from datetime import datetime, time, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError

import model_gateway
from app import (
    audit_routes,
    compose,
    connections,
    dashboard,
    erasure,
    private_mode_routes,
    quiet_hours,
    retention,
    scheduled_sends,
    template_store,
    todo,
)
from app.agent_contract import TranslateResponse
from app.audit import AuditAction, audit_row
from app.core.constants import EMBEDDING_DIM, LOCAL_EMBEDDING_DIM
from app.core.cursor import decode_cursor
from app.core.errors import DomainError, ErrorCode
from app.core.ownership import EVERYTHING, Scope
from app.core.providers import Provider
from app.core.ratelimit import PostgresCounters
from app.core.typed_names import TypedNames
from app.dashboard import SendRejectedError, list_dashboard_emails, snooze_email
from app.db.migrate import apply_pending, pending
from app.db.models import (
    AuditLog,
    AuthStatus,
    Chunk,
    ComposeDraft,
    DocType,
    Document,
    Embedding,
    LocalEmbedding,
    MaskingStatus,
    Message,
    ModelEgress,
    SentMessage,
    UserProfile,
)
from app.db.session import get_engine, get_sessionmaker
from app.gmail_send import SendError, SendOutcomeUnknownError, SentReply
from app.inbox_search import search_messages_hybrid
from app.jobs import claim_requested, request_draft
from app.ml.categorise import classify_pending
from app.normalise import pipeline
from app.private_mode import not_private
from app.quiet_hours import QuietHoursView
from app.rag.chunk import Piece
from app.rag.embedding_models import check_columns
from app.rag.ingest import store_chunks

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to a throwaway database")
CONCURRENT_WRITES = 10
# Long enough for a committed NOTIFY to reach a listener on the same machine.
NOTICE_WAIT_SECONDS = 0.3


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


def test_an_inbox_page_brings_every_email_of_its_threads_and_the_ones_with_no_thread():
    owner = uuid4()
    now = datetime.now(timezone.utc)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        emails = [Message(id=uuid4(), user_id=owner, gmail_message_id=f"thr-{uuid4()}", subject="s", thread_id=thread,
                          created_at=now - timedelta(minutes=age))
                  for thread, age in (("T", 1), ("T", 30), (None, 2), (None, 3))]
        async with get_sessionmaker()() as session, session.begin():
            session.add_all(emails)
        page = await list_dashboard_emails(Scope(owner_id=owner), "", 2, None)
        return {str(email.id) for email in emails[:3]}, [email.id for email in page.emails], page.nextCursor

    expected, listed, after = _run(scenario())
    assert set(listed) == expected and len(listed) == len(expected) and after is not None


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
    owner = Scope(owner_id=uuid4())
    source = f"upload://{uuid4()}.pdf"
    vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    async def upload_twice():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner.owner_id, email=f"{owner.owner_id}@example.com"))
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


def test_a_past_reply_older_than_a_year_goes_with_its_chunks_and_both_vectors_and_policies_stay():
    owner = Scope(owner_id=None)
    reply, policy = f"sent://{uuid4()}", f"upload://{uuid4()}.pdf"
    vector = [1.0] + [0.0] * (EMBEDDING_DIM - 1)

    async def scenario():
        await store_chunks(reply, "Reply", [Piece("Thanks, noted.")], scope=owner, doc_type=DocType.SENT_REPLY,
                           vectors=[vector])
        await store_chunks(policy, "Leave", [Piece("Old clause.")], scope=owner, doc_type=DocType.POLICY,
                           vectors=[vector])
        async with get_sessionmaker()() as session, session.begin():
            reply_chunk = await session.scalar(select(Chunk.id).join(Document).where(Document.source == reply))
            session.add(LocalEmbedding(chunk_id=reply_chunk, embedding=[1.0] + [0.0] * (LOCAL_EMBEDDING_DIM - 1),
                                       model_name="test"))
            await session.execute(update(Document).where(Document.source.in_([reply, policy]))
                                  .values(created_at=func.now() - timedelta(days=400)))
            await session.execute(retention._past_replies(retention.PAST_REPLY_DAYS))
        async with get_sessionmaker()() as session:
            sources = set((await session.scalars(select(Document.source).where(
                Document.source.in_([reply, policy])))).all())
            orphans = await session.scalar(select(func.count(LocalEmbedding.id)).where(
                LocalEmbedding.chunk_id == reply_chunk))
        return sources, orphans

    sources, orphans = _run(scenario())
    assert sources == {policy} and orphans == 0


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
        held_at = await _scalar(f"SELECT created_at FROM scheduled_send WHERE message_id = '{message.id}'")
        await scheduled_sends.hold(message.id, None, "two", first + timedelta(hours=1))
        rescheduled_at = await _scalar(f"SELECT created_at FROM scheduled_send WHERE message_id = '{message.id}'")
        rows = await _scalar(f"SELECT count(*) FROM scheduled_send WHERE message_id = '{message.id}'")
        waiting = (await scheduled_sends.states_for([message.id]))[message.id]
        await scheduled_sends.cancel_pending(message.id, scheduled_sends.CancelReason.THEY_REPLIED)
        after = (await scheduled_sends.states_for([message.id]))[message.id]
        return rows, waiting, after, rescheduled_at > held_at

    rows, waiting, after, is_restarted = _run(scenario())
    assert rows == 1 and waiting.send_at == datetime(2030, 1, 1, 2, tzinfo=timezone.utc)
    assert is_restarted  # "they replied since" counts from the reschedule
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
        await todo.dismiss_waiting(scope, waiting.id, is_dismissed=True)
        await todo.dismiss_email(scope, acting.id, is_dismissed=True)
        assert not await todo.dismiss_email(Scope(owner_id=uuid4()), acting.id, is_dismissed=True)
        after = await todo.todo_for(scope, f"{owner}@example.com")
        return before, after

    before, after = _run(scenario())
    assert (before.needsAction.total, before.needsReview.total, before.unsentDrafts.total) == (1, 1, 1)
    assert [w.threadId for w in before.waiting] == ["A"] and before.waiting[0].workingDays >= 3
    assert before.count == 1 + 1 + 1 + 1
    assert after.needsAction.total == 0 and after.waiting == []


def test_a_waiting_reply_opens_the_email_it_answered_and_an_answer_after_it_takes_it_off():
    owner = uuid4()
    now = datetime.now(timezone.utc)

    def received(thread: str, days_ago: int) -> Message:
        return Message(id=uuid4(), user_id=owner, gmail_message_id=f"wr-{uuid4()}", subject="s", thread_id=thread,
                       masking_status=MaskingStatus.COMPLETE, created_at=now - timedelta(days=days_ago))

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        asked = received("E", 10)
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([asked, received("F", 10), received("F", 1)])
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([SentMessage(user_id=owner, gmail_id=f"g-{uuid4()}", thread_id=thread,
                                         sent_at=now - timedelta(days=8), body_masked="Thanks.", remind=True)
                             for thread in ("E", "F")])
        return str(asked.id), await todo.todo_for(Scope(owner_id=owner), f"{owner}@example.com")

    asked_id, result = _run(scenario())
    assert [(w.threadId, w.email.id if w.email else None) for w in result.waiting] == [("E", asked_id)]


def test_a_todo_list_counts_every_email_though_it_shows_only_the_newest():
    owner = uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([Message(id=uuid4(), user_id=owner, gmail_message_id=f"many-{uuid4()}", subject="s",
                                     masking_status=MaskingStatus.COMPLETE, auth_status=AuthStatus.PASS,
                                     action_items=["Pay"]) for _ in range(todo.SECTION_LIMIT + 1)])
        return await todo.todo_for(Scope(owner_id=owner), f"{owner}@example.com")

    result = _run(scenario())
    assert (len(result.needsAction.emails), result.needsAction.total) == (todo.SECTION_LIMIT, todo.SECTION_LIMIT + 1)


def test_an_email_that_fits_every_todo_list_shows_once_in_the_most_urgent():
    owner = uuid4()
    now = datetime.now(timezone.utc)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            session.add(Message(id=uuid4(), user_id=owner, gmail_message_id=f"all-{uuid4()}", subject="s",
                                masking_status=MaskingStatus.COMPLETE, auth_status=AuthStatus.PASS,
                                action_items=["Pay"], needs_human_review=True, draft_reply="Hi",
                                generated_at=now - timedelta(days=2)))
        return await todo.todo_for(Scope(owner_id=owner), f"{owner}@example.com")

    result = _run(scenario())
    # Shown once, in the most urgent list: review comes before action and before an unsent draft.
    assert (result.needsReview.total, result.needsAction.total, result.unsentDrafts.total) == (1, 0, 0)
    assert result.count == 1


def test_remind_me_survives_the_listener_storing_the_send_first():
    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            message = Message(id=uuid4(), gmail_message_id=f"rm-{uuid4()}", masking_status=MaskingStatus.COMPLETE,
                              thread_id="t-race", subject="Invoice")
            session.add(message)
        async with get_sessionmaker()() as session, session.begin():
            session.add(SentMessage(gmail_id="g-race", thread_id="t-race", sent_at=datetime.now(timezone.utc),
                                    body_masked="Could you confirm, [PERSON_3]?"))
        reply = dashboard.OutgoingReply(stored="Could you confirm?", sent="Could you confirm?", restored=0)
        sent = SentReply(gmail_id="g-race", thread_id="t-race", message_id="<m>")
        await dashboard._record_send(message.id, message, reply, sent, remind=True)
        return message.id, await _scalar("SELECT remind::text || ' ' || message_id::text || ' ' || body_masked "
                                         "FROM sent_message WHERE gmail_id = 'g-race'")

    pk, row = _run(scenario())
    # The listener's masking (its own [PERSON_3]) gives way to AIMail's copy, which shares the vault.
    assert row == f"true {pk} Could you confirm?"


def _private_and_cloud_users() -> tuple[object, object]:
    """One user in Private mode and one on Gemini, each with an email about an invoice."""
    private, cloud = uuid4(), uuid4()

    async def seed():
        async with get_sessionmaker()() as session, session.begin():
            for user in (private, cloud):
                session.add(UserProfile(id=user, email=f"{user}@example.com"))
            await session.flush()
            for user in (private, cloud):
                session.add(Message(id=uuid4(), user_id=user, gmail_message_id=f"pv-{uuid4()}",
                                    subject="Invoice for the chairs", body_masked="Please confirm the invoice.",
                                    masking_status=MaskingStatus.COMPLETE))
        await private_mode_routes._save_choice(private, Provider.LOCAL)

    _run(seed())
    return private, cloud


def test_the_email_vector_backfill_leaves_out_private_mode_users():
    private, cloud = _private_and_cloud_users()

    async def owners():
        async with get_sessionmaker()() as session:
            return set((await session.scalars(select(Message.user_id).where(
                Message.user_id.in_([private, cloud]), not_private(Message.user_id)))).all())

    assert _run(owners()) == {cloud}


def test_a_private_inbox_search_finds_by_words_without_any_model(monkeypatch):
    private, _ = _private_and_cloud_users()

    async def no_model(*_args, **_kwargs):
        raise AssertionError("a Private mode inbox search asked a model for a vector")

    monkeypatch.setattr(model_gateway, "embed_query", no_model)
    found, _ = _run(search_messages_hybrid("invoice", 5, scope=Scope(private), provider=Provider.LOCAL, names=TypedNames(),
                                           gemini_vector=None))
    assert [message.user_id for message in found] == [private]


def test_switching_private_mode_on_forgets_the_gemini_vectors_of_the_users_emails():
    private, cloud = _private_and_cloud_users()

    async def scenario():
        await private_mode_routes._save_choice(private, Provider.GEMINI)
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(text("UPDATE messages SET embedding = :v WHERE user_id IN (:a, :b)"),
                                  {"v": str([0.0] * EMBEDDING_DIM), "a": private, "b": cloud})
        await private_mode_routes._save_choice(private, Provider.LOCAL)
        async with get_sessionmaker()() as session:
            rows = await session.execute(select(Message.user_id, Message.embedding.is_not(None))
                                         .where(Message.user_id.in_([private, cloud])))
            return dict(rows.all())

    assert _run(scenario()) == {private: False, cloud: True}


def test_private_mode_counts_as_decided_once_switched_either_way_or_put_off():
    switched, put_off, untouched = uuid4(), uuid4(), uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([UserProfile(id=user, email=f"{user}@example.com") for user in (switched, put_off, untouched)])
        await private_mode_routes._save_choice(switched, Provider.GEMINI)
        await private_mode_routes._put_off(put_off)
        return [await private_mode_routes._is_decided(user) for user in (switched, put_off, untouched)]

    assert _run(scenario()) == [True, True, False]


def _answered_and_sent() -> tuple[object, object, object]:
    """An email answered through AIMail (its reply in sent_message, linked) and one answered from Gmail."""
    owner, email, from_aimail, from_gmail = uuid4(), uuid4(), uuid4(), uuid4()
    now = datetime.now(timezone.utc)

    async def seed():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
            await session.flush()
            session.add(Message(id=email, user_id=owner, gmail_message_id=f"fu-{uuid4()}", thread_id=f"t-{email}",
                                subject="Invoice", from_addr="a@example.com", body_masked="Can you send it?",
                                masking_status=MaskingStatus.COMPLETE, sent_at=now - timedelta(days=5),
                                created_at=now - timedelta(days=6)))
            await session.flush()
            session.add_all([
                SentMessage(id=from_aimail, user_id=owner, gmail_id=f"g-{uuid4()}", message_id=email,
                            thread_id=f"t-{email}", sent_at=now - timedelta(days=5), body_masked="Could you confirm?"),
                SentMessage(id=from_gmail, user_id=owner, gmail_id=f"g-{uuid4()}", thread_id="t-gmail",
                            sent_at=now - timedelta(days=5), body_masked="Could you confirm?"),
            ])

    _run(seed())
    return Scope(owner), from_aimail, from_gmail


@pytest.fixture
def gmail_and_agent(monkeypatch):
    sends = []

    async def refine(_message, _thread, draft, instruction, _details, _tone):
        return {"draft": f"Following up: {draft}", "instruction": instruction}

    async def can_send(_user_id):
        return True

    async def send(gmail_id, to, subject, body, *, owner_id):
        sends.append(body)
        if body == "fail":
            raise SendError("Gmail refused")
        return SentReply(gmail_id=f"g-{uuid4()}", thread_id="t", message_id="<m>")

    monkeypatch.setattr(dashboard, "_refine", refine)
    monkeypatch.setattr(dashboard.connections, "can_send", can_send)
    monkeypatch.setattr(dashboard, "send_reply", send)
    return sends


def test_a_follow_up_is_drafted_from_the_reply_and_sent_as_the_threads_latest(gmail_and_agent):
    scope, from_aimail, _ = _answered_and_sent()

    async def scenario():
        draft, _details = await dashboard.draft_follow_up(str(from_aimail), scope=scope)
        await dashboard.send_follow_up(str(from_aimail), draft, scope=scope)
        try:
            await dashboard.send_follow_up(str(from_aimail), draft, scope=scope)
        except DomainError as again:
            refused = again.code
        linked = await _scalar(f"SELECT count(*) FROM sent_message WHERE user_id = '{scope.owner_id}' "
                               "AND message_id IS NOT NULL AND remind")
        return draft, refused, linked

    draft, refused, linked = _run(scenario())
    assert draft == "Following up: Could you confirm?"
    assert gmail_and_agent == [draft]
    assert refused == ErrorCode.ALREADY_SENT
    assert linked == 1  # the link moved to the follow-up, which is now tracked


def test_two_clicks_at_once_send_one_follow_up(gmail_and_agent):
    scope, from_aimail, _ = _answered_and_sent()

    async def scenario():
        return await asyncio.gather(*(dashboard.send_follow_up(str(from_aimail), "Following up.", scope=scope)
                                      for _ in range(2)), return_exceptions=True)

    outcomes = _run(scenario())
    assert gmail_and_agent == ["Following up."]
    assert sorted(type(outcome).__name__ for outcome in outcomes) == ["DomainError", "bool"]


def test_a_failed_follow_up_can_be_tried_again(gmail_and_agent):
    scope, from_aimail, _ = _answered_and_sent()

    async def scenario():
        try:
            await dashboard.send_follow_up(str(from_aimail), "fail", scope=scope)
        except SendError:
            pass
        await dashboard.send_follow_up(str(from_aimail), "Following up.", scope=scope)

    _run(scenario())
    assert gmail_and_agent == ["fail", "Following up."]


def test_a_reply_sent_from_gmail_is_followed_up_in_gmail(gmail_and_agent):
    scope, _, from_gmail = _answered_and_sent()
    with pytest.raises(SendRejectedError) as refused:
        _run(dashboard.draft_follow_up(str(from_gmail), scope=scope))
    assert refused.value.code == ErrorCode.FOLLOW_UP_UNAVAILABLE


def test_someone_elses_reply_cannot_be_followed_up(gmail_and_agent):
    _, from_aimail, _ = _answered_and_sent()
    assert _run(dashboard.send_follow_up(str(from_aimail), "Hi", scope=Scope(uuid4()))) is False


def test_a_search_across_users_on_gemini_leaves_out_private_mode_users():
    private, cloud = _private_and_cloud_users()
    found, _ = _run(search_messages_hybrid("invoice", 20, scope=EVERYTHING, provider=Provider.GEMINI, names=TypedNames(),
                                           gemini_vector=None))
    owners = {message.user_id for message in found}
    assert cloud in owners and private not in owners



@pytest.mark.parametrize("since", ["they_answered", "set_aside"])
def test_a_follow_up_is_refused_once_the_reply_is_no_longer_waiting(gmail_and_agent, since):
    scope, from_aimail, _ = _answered_and_sent()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            sent = await session.get(SentMessage, from_aimail)
            if since == "they_answered":
                session.add(Message(id=uuid4(), user_id=scope.owner_id, gmail_message_id=f"ans-{uuid4()}",
                                    thread_id=sent.thread_id, subject="Re: Invoice",
                                    masking_status=MaskingStatus.COMPLETE))
            else:
                sent.dismissed_at = datetime.now(timezone.utc)
        await dashboard.send_follow_up(str(from_aimail), "Following up.", scope=scope)

    with pytest.raises(SendRejectedError) as refused:
        _run(scenario())
    assert refused.value.code == ErrorCode.FOLLOW_UP_STALE
    assert gmail_and_agent == []


def test_marked_unread_stays_unread_while_the_open_view_refreshes(monkeypatch):
    async def no_templates(*_args, **_kwargs):
        return None

    monkeypatch.setattr(dashboard, "suggested_template_id", no_templates)
    pk = uuid4()

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(Message(id=pk, gmail_message_id=f"ur-{uuid4()}", subject="Invoice", body_masked="Hi",
                                masking_status=MaskingStatus.COMPLETE, generated_at=datetime.now(timezone.utc)))
        opened = await dashboard.read_email(str(pk), scope=EVERYTHING)
        await dashboard.mark_unread(str(pk), scope=EVERYTHING)
        refreshed = await dashboard.email_detail(str(pk), scope=EVERYTHING)
        is_read_after = await _scalar(f"SELECT read_at IS NOT NULL FROM messages WHERE id = '{pk}'")
        return opened.isRead, refreshed.isRead, is_read_after

    assert _run(scenario()) == (True, False, False)


# ---------- The inbox pages by whole conversations (specs/features/inbox-threads.md) ----------

def test_an_inbox_page_holds_whole_threads_so_none_splits_across_pages():
    owner = uuid4()
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def message(thread: str | None, minutes: int) -> Message:
        return Message(id=uuid4(), user_id=owner, gmail_message_id=f"thr-{uuid4()}", subject="s",
                       thread_id=thread, masking_status=MaskingStatus.COMPLETE,
                       created_at=base + timedelta(minutes=minutes), received_at=base + timedelta(minutes=minutes))

    # Thread a: an old email and the newest one; thread b in between; a lone email with no thread.
    old_a, b, lone, new_a = message("a", 0), message("b", 10), message(None, 20), message("a", 30)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([old_a, b, lone, new_a])
        scope = Scope(owner_id=owner)
        first = await list_dashboard_emails(scope, "", 2, None)
        second = await list_dashboard_emails(scope, "", 2, decode_cursor(first.nextCursor))
        return first, second

    first, second = _run(scenario())
    # Page 1: thread a (both emails, the old one included) and the lone email; page 2: thread b only.
    assert [e.id for e in first.emails] == [str(new_a.id), str(lone.id), str(old_a.id)]
    assert [e.id for e in second.emails] == [str(b.id)] and second.nextCursor is None


def test_a_row_says_you_replied_until_they_write_back():
    owner = uuid4()
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def message(minutes: int, **fields) -> Message:
        return Message(id=uuid4(), user_id=owner, gmail_message_id=f"ans-{uuid4()}", subject="s", thread_id="t",
                       masking_status=MaskingStatus.COMPLETE, created_at=base + timedelta(minutes=minutes),
                       received_at=base + timedelta(minutes=minutes), **fields)

    asked, answered_here, written_back = message(0), message(5, sent_at=base + timedelta(minutes=6)), message(40)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([asked, answered_here, written_back])
            # Answered from Gmail itself after the first email, before they wrote back.
            session.add(SentMessage(user_id=owner, gmail_id=f"g-{uuid4()}", thread_id="t",
                                    sent_at=base + timedelta(minutes=20), subject="s", body_masked="ok"))
        page = await list_dashboard_emails(Scope(owner_id=owner), "", 10, None)
        return {e.id: e.isAnswered for e in page.emails}

    answered = _run(scenario())
    assert answered == {str(asked.id): True, str(answered_here.id): True, str(written_back.id): False}


# ---------- Normalisation v2 (specs/features/normalisation-v2.md) ----------

def test_a_malay_email_gets_its_language_an_english_copy_and_a_deadline(monkeypatch):
    owner = uuid4()
    sent = datetime(2026, 10, 13, 2, tzinfo=timezone.utc)  # 10:00 in Kuala Lumpur

    async def call(_path, request, _answer):
        english = {"Permohonan cuti": "Leave request"}.get(request.text, "Please confirm by Friday.")
        return TranslateResponse(language="en", text=english, egress=[])

    async def gemini(_user_id):
        return "gemini"

    monkeypatch.setattr(pipeline.agent_client, "call", call)
    monkeypatch.setattr(pipeline, "provider_for", gemini)
    malay = Message(id=uuid4(), user_id=owner, gmail_message_id=f"nm-{uuid4()}", subject="Permohonan cuti",
                    body_masked="Saya ingin memohon cuti. Sila sahkan sebelum Jumaat.\n\nOn Mon, [PERSON_1] wrote:\n> old",
                    masking_status=MaskingStatus.COMPLETE, received_at=sent, created_at=sent)
    english = Message(id=uuid4(), user_id=owner, gmail_message_id=f"ne-{uuid4()}", subject="Hello",
                      body_masked="Thanks, all good.", masking_status=MaskingStatus.COMPLETE,
                      received_at=sent, created_at=sent)

    async def scenario():
        async with get_sessionmaker()() as session, session.begin():
            session.add(UserProfile(id=owner, email=f"{owner}@example.com"))
        async with get_sessionmaker()() as session, session.begin():
            session.add_all([malay, english])
        await pipeline.normalise_pending(limit=50)
        async with get_sessionmaker()() as session:
            return [await session.get(Message, m.id) for m in (malay, english)]

    stored_malay, stored_english = _run(scenario())
    assert (stored_malay.language, stored_malay.subject_en) == ("ms", "Leave request")
    assert stored_malay.own_text_en == "Please confirm by Friday."
    assert stored_malay.deadline_at == datetime(2026, 10, 16, 9, tzinfo=timezone.utc)  # Fri 17:00 in KL
    assert (stored_english.language, stored_english.own_text_en, stored_english.deadline_at) == ("en", None, None)


# ---------- Compose: a new email from a brief (specs/features/compose.md) ----------

VAULT_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
HARITH = "Harith Zulkifli <harith@keris.com.my>"
BRIEF = "Tell Harith we will raise the credit note by Friday. Call me on 012-345 6789 if needed."
WRITTEN = ("Dear [PERSON_1],\n\nWe will raise the credit note by Friday. Call me on [PHONE_1].\n\n"
           "Regards,\n[PERSON_900]")


@pytest.fixture
def composing(monkeypatch):
    """The agent, retrieval and Gmail stubbed; the database, vault and checks real."""
    monkeypatch.setenv("PII_VAULT_KEY", VAULT_KEY)
    seen: dict = {"requests": [], "sent": [], "send_delay": 0.0, "send_error": None, "meanwhile": None}

    async def gemini(_user_id):
        return Provider.GEMINI

    async def found(_query, **_kwargs):
        return [{"chunk_id": uuid4(), "content": "Credit notes are issued within 14 days.",
                 "similarity_score": 0.81, "source_title": "Refund policy"}]

    async def agent(path, request, answer):
        seen["requests"].append((path, request))
        if seen["meanwhile"]:
            await seen["meanwhile"]()
        draft = WRITTEN if path == "/compose" else WRITTEN.replace("[PHONE_1]", "[PHONE_1] or [PHONE_2]")
        return answer.model_validate({"subject": "Credit note for the pallet wrap", "draft": draft,
                                      "confidence": 0.93, "egress": [{"purpose": "draft", "provider": "gemini",
                                                                      "chars": 120, "sha256": "x", "hidden": {}}]})

    async def gmail(to, cc, subject, body, *, owner_id):
        await asyncio.sleep(seen["send_delay"])
        if seen["send_error"]:
            raise seen["send_error"]
        seen["sent"].append({"to": to, "cc": cc, "subject": subject, "body": body})
        return SentReply(gmail_id=f"gmail-{uuid4()}", thread_id="thread-new", message_id="<m@mail.gmail.com>")

    async def granted(_user_id):
        return True

    monkeypatch.setattr(compose, "model_for", gemini)
    monkeypatch.setattr(compose, "retrieve", found)
    monkeypatch.setattr(compose.agent_client, "call", agent)
    monkeypatch.setattr(compose, "send_new", gmail)
    monkeypatch.setattr(connections, "can_send", granted)
    return seen


async def _composer() -> UUID:
    owner = uuid4()
    async with get_sessionmaker()() as session, session.begin():
        session.add(UserProfile(id=owner, email=f"{owner}@example.com", display_name="Elyesa Tee"))
    return owner


def _fields(**typed: object) -> compose.ComposeFields:
    return compose.ComposeFields(**typed)


def test_a_new_email_is_stored_masked_written_from_placeholders_and_sent_with_the_details(composing):
    async def scenario():
        owner = await _composer()
        draft = await compose.create_draft(owner, _fields(to=[HARITH], brief=BRIEF))
        draft_id = UUID(draft.id)
        written = await compose.write(owner, draft_id, _fields())
        async with get_sessionmaker()() as session:
            row = await session.get(ComposeDraft, draft_id)
        body = written.body
        for detail in written.details:
            body = body.replace(detail.placeholder, detail.value)
        fields = _fields(to=[HARITH], subject=written.subject, body=body)
        sent = await compose.send(owner, draft_id, fields, remind=True)
        again = await compose.send(owner, draft_id, fields, remind=True)
        async with get_sessionmaker()() as session:
            copy = await session.scalar(select(SentMessage).where(SentMessage.user_id == owner))
            receipts = (await session.scalars(select(ModelEgress).where(
                ModelEgress.compose_draft_id == draft_id))).all()
            actions = (await session.scalars(select(AuditLog.action).where(AuditLog.user_id == owner))).all()
        return row, written, sent, again, copy, receipts, actions

    row, written, sent, again, copy, receipts, actions = _run(scenario())
    path, request = composing["requests"][0]
    # Stored, and sent to the model, as placeholders only.
    assert "012-345 6789" not in row.brief and "[PHONE_1]" in row.brief and row.pii_vault is not None
    assert path == "/compose" and "012-345 6789" not in request.brief and "[PHONE_1]" in request.brief
    assert request.recipients == ["[PERSON_1]"] and request.sign_off == "[PERSON_900]"
    assert "Credit notes are issued within 14 days." in request.rag_context
    assert written.subject == "Credit note for the pallet wrap" and written.sources[0].label == "Refund policy"
    # Sent once, with every detail filled in, to the address as typed.
    assert len(composing["sent"]) == 1
    email = composing["sent"][0]
    assert email["to"] == [HARITH] and "Dear Harith Zulkifli" in email["body"]
    assert "012-345 6789" in email["body"] and "Elyesa Tee" in email["body"] and "[" not in email["body"]
    assert sent.state == "sent" and again.state == "sent"
    # Recorded masked for the waiting list, with its receipt and its trail.
    assert copy.message_id is None and copy.remind is True and "[PHONE_1]" in copy.body_masked
    assert "012-345 6789" not in copy.body_masked
    assert len(receipts) == 1
    assert {"compose_written", "compose_sent"} <= set(actions)


def test_two_sends_of_one_draft_reach_gmail_once(composing):
    composing["send_delay"] = 0.3

    async def scenario():
        owner = await _composer()
        fields = _fields(to=[HARITH], subject="Hello", body="Hi Harith, a note.")
        draft_id = UUID((await compose.create_draft(owner, fields)).id)
        return await asyncio.gather(compose.send(owner, draft_id, fields, remind=None),
                                    compose.send(owner, draft_id, fields, remind=None),
                                    return_exceptions=True)

    results = _run(scenario())
    refused = [result for result in results if isinstance(result, DomainError)]
    assert len(composing["sent"]) == 1
    assert len(refused) == 1 and refused[0].code == ErrorCode.SEND_IN_PROGRESS


def test_a_refused_send_can_be_sent_again_and_an_unknown_one_waits_for_the_user(composing):
    async def scenario():
        owner = await _composer()
        fields = _fields(to=[HARITH], subject="Hello", body="Hi Harith.")
        draft_id = UUID((await compose.create_draft(owner, fields)).id)
        composing["send_error"] = SendError("gmail said no")
        with pytest.raises(SendError):
            await compose.send(owner, draft_id, fields, remind=None)
        released = (await compose.get_draft(owner, draft_id)).state
        composing["send_error"] = SendOutcomeUnknownError("no answer")
        with pytest.raises(SendOutcomeUnknownError):
            await compose.send(owner, draft_id, fields, remind=None)
        with pytest.raises(DomainError) as editing:
            await compose.update_draft(owner, draft_id, _fields(body="changed"))
        # The request is over, so it can be settled at once rather than after the in-flight window.
        unknown = (await compose.get_draft(owner, draft_id)).state
        settled = await compose.settle(owner, draft_id, compose.SettleOutcome.NOT_SENT)
        return released, editing.value.code, unknown, settled.state

    released, editing, unknown, settled = _run(scenario())
    assert released == "draft"
    assert editing == ErrorCode.SEND_IN_PROGRESS
    assert unknown == "outcome_unknown" and settled == "draft"


def test_a_send_is_refused_before_gmail_for_bad_addresses_or_unfillable_placeholders(composing):
    async def scenario():
        owner = await _composer()
        draft_id = UUID((await compose.create_draft(owner, _fields(subject="Hi", body="x"))).id)
        codes = []
        for fields in (_fields(to=["a@b.com\r\nBcc: c@d.com"], subject="Hi", body="Hello"),
                       _fields(to=[HARITH], subject="Hi", body="Hello [PHONE_7]"),
                       _fields(to=[HARITH], subject="Hi", body="Hello [EMAIL_REDACTED]")):
            with pytest.raises(DomainError) as refused:
                await compose.send(owner, draft_id, fields, remind=None)
            codes.append(refused.value.code)
        return codes, (await compose.get_draft(owner, draft_id)).state

    codes, state = _run(scenario())
    assert codes == [ErrorCode.INVALID_RECIPIENTS, ErrorCode.UNRESOLVED_PLACEHOLDERS, ErrorCode.REDACTION_MARKERS]
    assert state == "draft" and composing["sent"] == []


def test_another_users_draft_reads_as_missing(composing):
    async def scenario():
        owner, stranger = await _composer(), await _composer()
        draft_id = UUID((await compose.create_draft(owner, _fields(brief=BRIEF))).id)
        codes = []
        for attempt in (compose.get_draft(stranger, draft_id),
                        compose.update_draft(stranger, draft_id, _fields(body="mine now")),
                        compose.delete_draft(stranger, draft_id),
                        compose.send(stranger, draft_id, _fields(to=[HARITH], subject="Hi", body="Hi"),
                                     remind=None)):
            with pytest.raises(DomainError) as refused:
                await attempt
            codes.append(refused.value.code)
        return codes, await compose.list_drafts(stranger)

    codes, listed = _run(scenario())
    assert codes == [ErrorCode.NOT_FOUND] * 4
    assert listed.drafts == [] and listed.sent == []


def test_disconnecting_gmail_erases_drafts_and_old_sent_ones_expire(composing):
    async def scenario():
        owner, other = await _composer(), await _composer()
        await compose.create_draft(owner, _fields(brief=BRIEF))
        kept = UUID((await compose.create_draft(other, _fields(brief=BRIEF))).id)
        old = UUID((await compose.create_draft(other, _fields(brief="old"))).id)
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(update(ComposeDraft).where(ComposeDraft.id == old).values(
                sent_at=func.now() - timedelta(days=retention.SENT_COMPOSE_DAYS + 1)))
            counts = await erasure.erase(session, owner, erasure.Subject.MAILBOX)
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(retention._sent_compose_drafts(retention.SENT_COMPOSE_DAYS))
        async with get_sessionmaker()() as session:
            left = set((await session.scalars(select(ComposeDraft.id).where(
                ComposeDraft.user_id.in_([owner, other])))).all())
        return counts, left, kept

    counts, left, kept = _run(scenario())
    assert counts["compose_draft"] == 1
    assert left == {kept}


def test_a_number_typed_in_a_refine_instruction_reaches_the_sent_email(composing):
    async def scenario():
        owner = await _composer()
        draft_id = UUID((await compose.create_draft(owner, _fields(to=[HARITH], brief=BRIEF))).id)
        await compose.write(owner, draft_id, _fields())
        refined = await compose.refine(owner, draft_id, "add my office line 03-1234 5678", _fields())
        body = refined.body
        for detail in refined.details:
            body = body.replace(detail.placeholder, detail.value)
        await compose.send(owner, draft_id, _fields(to=[HARITH], subject=refined.subject, body=body), remind=None)
        return refined

    refined = _run(scenario())
    _, request = composing["requests"][-1]
    assert "03-1234 5678" not in request.instruction and "[PHONE_2]" in request.instruction
    assert "[PHONE_2]" in refined.body
    assert "03-1234 5678" in composing["sent"][0]["body"]


def test_an_edit_made_elsewhere_while_writing_is_kept_and_the_answer_refused(composing):
    async def scenario():
        owner = await _composer()
        draft_id = UUID((await compose.create_draft(owner, _fields(to=[HARITH], brief=BRIEF))).id)

        async def edited_in_another_tab():
            await compose.update_draft(owner, draft_id, _fields(body="My own words."))

        composing["meanwhile"] = edited_in_another_tab
        with pytest.raises(DomainError) as refused:
            await compose.write(owner, draft_id, _fields())
        return refused.value.code, (await compose.get_draft(owner, draft_id)).body

    code, body = _run(scenario())
    assert code == ErrorCode.CONFLICT and body == "My own words."


def test_retention_never_deletes_a_draft_that_may_have_been_sent(composing):
    async def scenario():
        owner = await _composer()
        claimed = UUID((await compose.create_draft(owner, _fields(brief="claimed"))).id)
        idle = UUID((await compose.create_draft(owner, _fields(brief="idle"))).id)
        async with get_sessionmaker()() as session, session.begin():
            await session.execute(update(ComposeDraft).where(ComposeDraft.id.in_([claimed, idle])).values(
                updated_at=func.now() - timedelta(days=400)))
            await session.execute(update(ComposeDraft).where(ComposeDraft.id == claimed).values(
                send_claimed_at=func.now() - timedelta(days=400)))
            await session.execute(retention._unsent_compose_drafts(30))
        async with get_sessionmaker()() as session:
            return set((await session.scalars(select(ComposeDraft.id).where(ComposeDraft.user_id == owner))).all()), claimed

    left, claimed = _run(scenario())
    assert left == {claimed}


def test_a_change_to_an_email_is_announced_and_writing_the_same_value_back_is_not():
    async def scenario() -> list[str]:
        kinds: list[str] = []
        async with get_engine().connect() as listening:
            raw = (await listening.get_raw_connection()).driver_connection
            await raw.add_listener("mailbox_changed", lambda *notice: kinds.append(json.loads(notice[3])["kind"]))
            message = Message(id=uuid4(), gmail_message_id=f"ev-{uuid4()}", subject="s",
                              masking_status=MaskingStatus.COMPLETE)
            async with get_sessionmaker()() as session, session.begin():
                session.add(message)
            for read_at in (None, datetime.now(timezone.utc)):
                async with get_sessionmaker()() as session, session.begin():
                    await session.execute(update(Message).where(Message.id == message.id).values(read_at=read_at))
            await asyncio.sleep(NOTICE_WAIT_SECONDS)
        return kinds

    assert _run(scenario()) == ["new", "state"]
