"""The public status page's data (specs/features/todo-redesign-and-status.md): which part works, nothing more."""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.health import (
    CHECK_TIMEOUT_SECONDS,
    STATUS_PATH,
    database_answers,
    presidio_answers,
)
from app.db.models import MailboxConnection
from app.db.session import get_sessionmaker

# Only the listener writes watch_expires_at, renewing daily (listener/main.go), and Gmail sets it this far
# ahead; updated_at won't do, since a sign-in stamps it too and would make a stopped listener look alive.
GMAIL_WATCH_LIFETIME = timedelta(days=7)
LISTENER_DEGRADED_AFTER = timedelta(hours=26)
LISTENER_DOWN_AFTER = timedelta(hours=50)
# Public and unauthenticated: visitors must not be able to make it call Presidio or the agent more often.
CACHE_SECONDS = 15.0


class PartState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


class Parts(BaseModel):
    backend: PartState
    database: PartState
    masking: PartState
    drafting: PartState
    listener: PartState


class ServiceStatus(BaseModel):
    checkedAt: str
    parts: Parts


def _state(is_working: bool) -> PartState:
    return PartState.OK if is_working else PartState.DOWN


async def agent_answers() -> bool:
    try:
        async with httpx.AsyncClient(timeout=CHECK_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{get_settings().email_agent_url}/healthz")
    except httpx.HTTPError:
        return False
    return response.is_success


async def newest_listener_check_in() -> datetime | None:
    """When the listener last renewed a connected mailbox's watch; None when none, or the database can't say."""
    try:
        async with asyncio.timeout(CHECK_TIMEOUT_SECONDS), get_sessionmaker()() as session:
            expires = await session.scalar(select(func.max(MailboxConnection.watch_expires_at))
                                           .where(MailboxConnection.needs_reconnect.is_(False)))
    except (SQLAlchemyError, OSError, TimeoutError):
        return None
    return expires - GMAIL_WATCH_LIFETIME if expires else None


def listener_state(newest: datetime | None, now: datetime) -> PartState:
    # No connected mailbox, or no answer: "working" can't be claimed.
    if newest is None:
        return PartState.DEGRADED
    if now - newest > LISTENER_DOWN_AFTER:
        return PartState.DOWN
    if now - newest > LISTENER_DEGRADED_AFTER:
        return PartState.DEGRADED
    return PartState.OK


async def _check() -> ServiceStatus:
    database, masking, drafting, newest = await asyncio.gather(
        database_answers(), presidio_answers(), agent_answers(), newest_listener_check_in())
    now = datetime.now(timezone.utc)
    parts = Parts(backend=PartState.OK, database=_state(database), masking=_state(masking),
                  drafting=_state(drafting), listener=listener_state(newest, now))
    return ServiceStatus(checkedAt=now.isoformat(), parts=parts)


class _Cache:
    def __init__(self) -> None:
        self.status: ServiceStatus | None = None
        self.expires = 0.0
        self.lock = asyncio.Lock()

    async def get(self) -> ServiceStatus:
        # One check at a time: a burst of visitors waits for it instead of starting its own.
        async with self.lock:
            if self.status is None or time.monotonic() >= self.expires:
                self.status = await _check()
                self.expires = time.monotonic() + CACHE_SECONDS
            return self.status


_cache = _Cache()
router = APIRouter()


@router.get(STATUS_PATH)
async def service_status() -> ServiceStatus:
    return await _cache.get()
