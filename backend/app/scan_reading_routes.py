"""Settings > Scanned attachments (specs/features/signature-detection.md). Per signed-in user only.

The listener reads the choice from user_preferences.scan_reading; this only stores it.
"""

from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.account_routes import account_user_id
from app.audit import AuditAction, audit
from app.core.config import get_settings
from app.core.errors import DomainError, ErrorCode
from app.db.models import UserPreferences
from app.db.session import get_sessionmaker

router = APIRouter()


class ScanReading(StrEnum):
    """Values of user_preferences.scan_reading (migration 0036); the listener mirrors them."""

    LOCAL = "local"
    CHECKED = "checked"


class ScanReadingView(BaseModel):
    # Whether the company set up the local vision model that checked scans need.
    available: bool
    mode: ScanReading


class ScanReadingBody(BaseModel):
    mode: ScanReading


def is_check_offered() -> bool:
    return bool(get_settings().local_vision_model.strip())


async def _chosen(user_id: UUID) -> ScanReading:
    async with get_sessionmaker()() as session:
        chosen = await session.scalar(select(UserPreferences.scan_reading).where(UserPreferences.user_id == user_id))
    return ScanReading(chosen or ScanReading.LOCAL)


async def _save(user_id: UUID, mode: ScanReading) -> None:
    statement = insert(UserPreferences).values(user_id=user_id, scan_reading=mode)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(statement.on_conflict_do_update(
            index_elements=["user_id"], set_={"scan_reading": mode, "updated_at": func.now()}))


@router.get("/settings/scan-reading")
async def get_scan_reading(request: Request) -> ScanReadingView:
    return ScanReadingView(available=is_check_offered(), mode=await _chosen(account_user_id(request)))


@router.put("/settings/scan-reading")
async def put_scan_reading(body: ScanReadingBody, request: Request) -> ScanReadingView:
    user_id = account_user_id(request)
    # Going back to local is always allowed, so nobody is stuck on a check the company removed.
    if body.mode == ScanReading.CHECKED and not is_check_offered():
        raise DomainError(ErrorCode.SCAN_CHECK_UNAVAILABLE)
    await _save(user_id, body.mode)
    await audit(AuditAction.SCAN_READING, user_id=user_id, mode=body.mode.value)
    return ScanReadingView(available=is_check_offered(), mode=body.mode)
