"""Live inbox (specs/features/live-inbox.md): the event stream and what feeds it."""

import asyncio
from uuid import uuid4

import pytest

from app import events as live
from app.core.auth import Principal
from app.events import (
    PING,
    RESYNC,
    EventKind,
    MailboxEvent,
    MailboxEvents,
    StreamLimitError,
    parse_notice,
)
from tests.conftest import AUTH_HEADERS


async def _never() -> None:
    await asyncio.Event().wait()


@pytest.fixture
def quiet_listener(monkeypatch):
    """No database: the listener task just waits, so subscribe() can start it in a test loop."""
    monkeypatch.setattr(MailboxEvents, "_listen", lambda _self: _never())


def test_an_event_reaches_only_its_owners_streams(quiet_listener):
    async def scenario():
        source = MailboxEvents()
        alice, bob = uuid4(), uuid4()
        a_tab, a_phone, b_tab = source.subscribe(alice), source.subscribe(alice), source.subscribe(bob)
        source.publish(alice, MailboxEvent(EventKind.NEW, "m1"))
        got = [a_tab.get_nowait(), a_phone.get_nowait()]
        await source.close()
        return got, b_tab.empty()

    got, bob_empty = asyncio.run(scenario())
    assert got == [MailboxEvent(EventKind.NEW, "m1")] * 2 and bob_empty


def test_a_tab_that_stops_reading_gets_one_resync_not_a_backlog(quiet_listener, monkeypatch):
    monkeypatch.setattr(live, "QUEUE_SIZE", 2)

    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        queue = source.subscribe(owner)
        for index in range(5):
            source.publish(owner, MailboxEvent(EventKind.STATE, f"m{index}"))
        drained = []
        while not queue.empty():
            drained.append(queue.get_nowait())
        await source.close()
        return drained

    assert asyncio.run(scenario()) == [RESYNC]


def test_the_fourth_stream_of_a_user_is_refused_and_the_first_three_keep_working(quiet_listener):
    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        opened = [source.subscribe(owner) for _ in range(live.STREAMS_PER_USER)]
        with pytest.raises(StreamLimitError):
            source.subscribe(owner)
        source.publish(owner, MailboxEvent(EventKind.NEW, "m1"))
        delivered = sum(not queue.empty() for queue in opened)
        await source.close()
        return delivered

    assert asyncio.run(scenario()) == live.STREAMS_PER_USER


def test_the_listener_runs_only_while_someone_is_connected(quiet_listener):
    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        before = source.is_listening
        queue = source.subscribe(owner)
        during = source.is_listening
        source.unsubscribe(owner, queue)
        return before, during, source.is_listening

    assert asyncio.run(scenario()) == (False, True, False)


def test_a_reopened_listener_tells_every_tab_to_refetch(monkeypatch):
    class Connection:
        def add_termination_listener(self, _callback):
            pass

        async def add_listener(self, _channel, _callback):
            pass

        async def close(self):
            pass

    async def connect(_dsn, timeout):
        return Connection()

    monkeypatch.setattr(live.asyncpg, "connect", connect)
    monkeypatch.setattr(live, "_dsn", lambda: "postgresql://unused")

    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        queue = source.subscribe(owner)
        got = await asyncio.wait_for(queue.get(), timeout=2)
        await source.close()
        return got

    assert asyncio.run(scenario()) == RESYNC


@pytest.mark.parametrize("payload", [
    "not json",
    '{"user_id": null, "message_id": "5f0c9a2e-1b2c-4d3e-8f9a-0b1c2d3e4f5a", "kind": "new"}',  # owner-less row
    '{"user_id": "5f0c9a2e-1b2c-4d3e-8f9a-0b1c2d3e4f5a", "message_id": "x", "kind": "new"}',
    '{"user_id": "5f0c9a2e-1b2c-4d3e-8f9a-0b1c2d3e4f5a", "message_id": "5f0c9a2e-1b2c-4d3e-8f9a-0b1c2d3e4f5a", "kind": "body"}',
])
def test_a_notice_that_is_not_two_ids_and_a_kind_is_dropped(payload):
    assert parse_notice(payload) is None


def test_a_notice_carries_ids_only_and_nothing_else_is_kept():
    owner, message = uuid4(), uuid4()
    payload = f'{{"user_id": "{owner}", "message_id": "{message}", "kind": "draft", "subject": "leaked?"}}'
    assert parse_notice(payload) == (owner, MailboxEvent(EventKind.DRAFT, str(message)))


def test_the_body_opens_with_a_retry_hint_then_events_then_a_ping_while_quiet(monkeypatch):
    monkeypatch.setattr(live, "KEEPALIVE_SECONDS", 0.01)

    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        queue: asyncio.Queue[MailboxEvent] = asyncio.Queue()
        queue.put_nowait(MailboxEvent(EventKind.NEW, "m1"))
        lines = live.event_lines(owner, queue, source)
        return [await anext(lines) for _ in range(3)]

    retry, event, ping = asyncio.run(scenario())
    assert retry == "retry: 3000\n\n"
    assert event == 'id: 1\nevent: mailbox\ndata: {"kind": "new", "messageId": "m1"}\n\n'
    assert ping == PING


def test_streams_end_when_the_process_is_told_to_stop_so_the_drain_finishes():
    async def scenario():
        source = MailboxEvents()
        owner = uuid4()
        queue: asyncio.Queue[MailboxEvent] = asyncio.Queue()
        source._queues[owner] = {queue}
        lines = live.event_lines(owner, queue, source)
        await anext(lines)  # the retry hint
        source.end_streams()
        return [line async for line in lines], source.stream_count

    assert asyncio.run(scenario()) == ([], 0)


def test_scripts_with_the_service_token_have_no_stream(api_client):
    response = api_client.get("/events", headers=AUTH_HEADERS)
    assert response.status_code == 404


def test_a_signed_in_user_streams_their_events_and_a_fourth_tab_is_refused(api_client, monkeypatch):
    owner = uuid4()
    monkeypatch.setattr("app.main.principal_of", lambda _request: Principal(email="a@b.c", user_id=owner))
    subscribed = []
    monkeypatch.setattr(live.events, "subscribe", lambda user_id: subscribed.append(user_id) or asyncio.Queue())

    # The body generator has its own test; here it ends after one event so the test client can finish.
    async def one_event(user_id, _queue, _source):
        yield MailboxEvent(EventKind.NEW, "m1").sse(1)

    monkeypatch.setattr("app.main.event_lines", one_event)
    response = api_client.get("/events", headers=AUTH_HEADERS)
    assert response.status_code == 200 and subscribed == [owner]
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.text == 'id: 1\nevent: mailbox\ndata: {"kind": "new", "messageId": "m1"}\n\n'

    def refuse(_user_id):
        raise StreamLimitError

    monkeypatch.setattr(live.events, "subscribe", refuse)
    assert api_client.get("/events", headers=AUTH_HEADERS).status_code == 429
