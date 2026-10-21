"""Live inbox (specs/features/live-inbox.md): a change to an email reaches the open dashboard at once.

A trigger on `messages` raises NOTIFY on `mailbox_changed` with ids only (migration 0046). While at
least one dashboard is connected, one asyncpg LISTEN connection fans each notice out to its owner's
streams; it is opened with the first stream and closed with the last, so an idle API holds nothing.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

import asyncpg

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CHANNEL = "mailbox_changed"
# Vercel's rewrite drops an origin that stays silent for 120 s; a comment every 25 s keeps a 4x margin.
KEEPALIVE_SECONDS = 25
# How long the browser waits before reconnecting after a drop (a deploy, say).
RETRY_MS = 3_000
CONNECT_TIMEOUT_SECONDS = 10
RECONNECT_SECONDS = 5
# A tab that stops reading gets one "resync" instead of a growing backlog.
QUEUE_SIZE = 100
STREAMS_PER_USER = 3
STREAMS_IN_ALL = 200
PING = ": ping\n\n"


class EventKind(StrEnum):
    NEW = "new"
    DRAFT = "draft"
    STATE = "state"
    # The stream or the listener (re)opened: refetch, something may have been missed meanwhile.
    RESYNC = "resync"
    # Never sent: ends a stream when the process is stopping, so the browser reconnects to the next one.
    CLOSE = "close"


@dataclass(frozen=True)
class MailboxEvent:
    kind: EventKind
    message_id: str | None = None

    def sse(self, sequence: int) -> str:
        data = {"kind": self.kind.value, "messageId": self.message_id}
        return f"id: {sequence}\nevent: mailbox\ndata: {json.dumps(data)}\n\n"


RESYNC = MailboxEvent(EventKind.RESYNC)
CLOSE = MailboxEvent(EventKind.CLOSE)


class StreamLimitError(Exception):
    """This user, or the whole process, already holds as many open streams as allowed."""


def parse_notice(payload: str) -> tuple[UUID, MailboxEvent] | None:
    """The trigger's JSON: user_id, message_id, kind. Anything else is dropped, never guessed at."""
    try:
        notice = json.loads(payload)
        user_id = UUID(notice["user_id"])
        event = MailboxEvent(EventKind(notice["kind"]), str(UUID(notice["message_id"])))
    except (ValueError, TypeError, KeyError):
        return None
    return user_id, event


def _offer(queue: asyncio.Queue[MailboxEvent], event: MailboxEvent) -> None:
    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        while not queue.empty():
            queue.get_nowait()
        queue.put_nowait(RESYNC)


def _dsn() -> str:
    # The plain URL asyncpg takes; the SQLAlchemy driver prefix is only for the engine.
    return get_settings().database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


class MailboxEvents:
    """Per-user queues of events, fed by one LISTEN connection that lives only while someone is connected."""

    def __init__(self) -> None:
        self._queues: dict[UUID, set[asyncio.Queue[MailboxEvent]]] = {}
        self._listener: asyncio.Task[None] | None = None

    @property
    def stream_count(self) -> int:
        return sum(len(queues) for queues in self._queues.values())

    @property
    def is_listening(self) -> bool:
        return self._listener is not None

    def subscribe(self, user_id: UUID) -> asyncio.Queue[MailboxEvent]:
        mine = self._queues.setdefault(user_id, set())
        if len(mine) >= STREAMS_PER_USER or self.stream_count >= STREAMS_IN_ALL:
            raise StreamLimitError
        queue: asyncio.Queue[MailboxEvent] = asyncio.Queue(QUEUE_SIZE)
        mine.add(queue)
        if self._listener is None:
            self._listener = asyncio.create_task(self._listen(), name="mailbox events")
        return queue

    def unsubscribe(self, user_id: UUID, queue: asyncio.Queue[MailboxEvent]) -> None:
        mine = self._queues.get(user_id, set())
        mine.discard(queue)
        if not mine:
            self._queues.pop(user_id, None)
        if not self._queues and self._listener is not None:
            self._listener.cancel()
            self._listener = None

    async def close(self) -> None:
        if self._listener is None:
            return
        self._listener.cancel()
        with suppress(asyncio.CancelledError):
            await self._listener
        self._listener = None

    def publish(self, user_id: UUID, event: MailboxEvent) -> None:
        for queue in self._queues.get(user_id, ()):
            _offer(queue, event)

    def publish_all(self, event: MailboxEvent) -> None:
        for user_id in list(self._queues):
            self.publish(user_id, event)

    def end_streams(self) -> None:
        """Open streams would hold a graceful shutdown open; each ends now and the browser reconnects."""
        self.publish_all(CLOSE)

    def _on_notice(self, _connection: object, _pid: int, _channel: str, payload: str) -> None:
        parsed = parse_notice(payload)
        if parsed is None:
            return
        self.publish(*parsed)

    async def _listen(self) -> None:
        """Hold the LISTEN connection, reopening it when it drops; each (re)open tells every tab to refetch."""
        while True:
            try:
                await self._listen_once()
            except (OSError, asyncpg.PostgresError, asyncpg.InterfaceError, TimeoutError) as exc:
                logger.warning("mailbox events: listener lost (%s), retrying in %ss",
                               type(exc).__name__, RECONNECT_SECONDS)
            await asyncio.sleep(RECONNECT_SECONDS)

    async def _listen_once(self) -> None:
        lost = asyncio.Event()
        connection = await asyncpg.connect(_dsn(), timeout=CONNECT_TIMEOUT_SECONDS)
        try:
            connection.add_termination_listener(lambda _connection: lost.set())
            await connection.add_listener(CHANNEL, self._on_notice)
            self.publish_all(RESYNC)
            await lost.wait()
        finally:
            with suppress(OSError, asyncpg.PostgresError, asyncpg.InterfaceError):
                await connection.close()


events = MailboxEvents()


async def event_lines(user_id: UUID, queue: asyncio.Queue[MailboxEvent], source: MailboxEvents) -> AsyncIterator[str]:
    """The response body: a retry hint, then events as they come, with a comment line while quiet."""
    sequence = 0
    try:
        yield f"retry: {RETRY_MS}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), KEEPALIVE_SECONDS)
            except TimeoutError:
                yield PING
                continue
            if event.kind is EventKind.CLOSE:
                return
            sequence += 1
            yield event.sse(sequence)
    finally:
        source.unsubscribe(user_id, queue)
