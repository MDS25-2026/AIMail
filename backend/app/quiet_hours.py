"""Quiet hours (specs/features/quiet-hours-send-later.md): when not to send, as a suggestion only.

The company default is the row with no user; a user's own row replaces it for them. The dashboard
works out "it's 11:40pm for them" from these and the sender's offset; the server only stores them.
"""

from datetime import time
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import QuietHours
from app.db.session import get_sessionmaker

ISO_WEEKDAYS = range(1, 8)  # 1 = Monday, as holding replies count work days


class QuietHoursView(BaseModel):
    start: time
    end: time
    # ISO weekdays that are quiet all day: {6, 7} for most states, {5, 6} for Kelantan and others.
    weekendDays: list[int] = Field(max_length=7)
    timezone: str

    @field_validator("weekendDays")
    @classmethod
    def _iso_weekdays(cls, days: list[int]) -> list[int]:
        if any(day not in ISO_WEEKDAYS for day in days):
            raise ValueError("weekend days are ISO weekdays, 1 (Monday) to 7 (Sunday)")
        return sorted(set(days))

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, zone: str) -> str:
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {zone!r}") from exc
        return zone

    @model_validator(mode="after")
    def _a_window(self) -> "QuietHoursView":
        if self.start == self.end:
            raise ValueError("quiet hours must start and end at different times")
        return self


class QuietHoursSettings(BaseModel):
    company: QuietHoursView
    # None: the user follows the company default.
    personal: QuietHoursView | None
    effective: QuietHoursView


def _view(row: QuietHours) -> QuietHoursView:
    return QuietHoursView(start=row.starts, end=row.ends, weekendDays=list(row.weekend_days), timezone=row.timezone)


def _columns(view: QuietHoursView) -> dict:
    return {"starts": view.start, "ends": view.end, "weekend_days": view.weekendDays, "timezone": view.timezone}


async def _row(user_id: UUID | None) -> QuietHours | None:
    owner = QuietHours.user_id.is_(None) if user_id is None else QuietHours.user_id == user_id
    async with get_sessionmaker()() as session:
        return await session.scalar(select(QuietHours).where(owner))


async def company_default() -> QuietHoursView:
    row = await _row(None)
    return _view(row) if row else QuietHoursView(start=time(21), end=time(8), weekendDays=[6, 7],
                                                  timezone="Asia/Kuala_Lumpur")


async def settings_for(user_id: UUID) -> QuietHoursSettings:
    company = await company_default()
    own = await _row(user_id)
    personal = _view(own) if own else None
    return QuietHoursSettings(company=company, personal=personal, effective=personal or company)


async def save(user_id: UUID | None, view: QuietHoursView) -> None:
    """A user's own quiet hours, or the company default when user_id is None."""
    statement = insert(QuietHours).values(user_id=user_id, **_columns(view))
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(statement.on_conflict_do_update(
            index_elements=["user_id"], set_={**_columns(view), "updated_at": func.now()}))


async def follow_company(user_id: UUID) -> None:
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(delete(QuietHours).where(QuietHours.user_id == user_id))
