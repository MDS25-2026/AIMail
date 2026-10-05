"""Holding reply settings and the record of what went out in the user's name."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.account_routes import AccountError
from app.audit import audit
from app.core.auth import principal_of
from app.db.models import HoldingReply, HoldingReplySettings, Message
from app.db.session import get_sessionmaker
from app.holding_reply import InvalidSettingsError, Refusal, SettingsBody, validate

router = APIRouter()

MAX_LIST = 100


class HoldingReplyView(BaseModel):
    id: str
    emailId: str
    recipient: str
    language: str
    scheduledFor: datetime
    sentAt: datetime | None
    cancelledReason: str | None
    subject: str


def _user_id(request: Request) -> UUID:
    user_id = principal_of(request).user_id
    if user_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, AccountError.ACCOUNT_ONLY)
    return user_id


def _to_body(row: HoldingReplySettings) -> SettingsBody:
    return SettingsBody(
        enabled=row.enabled, activeWhen=row.active_when, workDays=row.work_days, workStart=row.work_start,
        workEnd=row.work_end, timezone=row.timezone, leaveFrom=row.leave_from, leaveUntil=row.leave_until,
        audience=row.audience, scope=row.scope, cooldownDays=row.cooldown_days, templates=row.templates,
        defaultLanguage=row.default_language,
    )


@router.get("/settings/holding-reply")
async def get_settings_route(request: Request) -> SettingsBody:
    async with get_sessionmaker()() as session:
        row = await session.get(HoldingReplySettings, _user_id(request))
    return _to_body(row) if row else SettingsBody()


@router.put("/settings/holding-reply")
async def put_settings_route(body: SettingsBody, request: Request) -> SettingsBody:
    user_id = _user_id(request)
    try:
        validate(body)
    except InvalidSettingsError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.code) from exc
    values = {
        "enabled": body.enabled, "active_when": body.activeWhen, "work_days": body.workDays,
        "work_start": body.workStart, "work_end": body.workEnd, "timezone": body.timezone,
        "leave_from": body.leaveFrom, "leave_until": body.leaveUntil, "audience": body.audience,
        "scope": body.scope, "cooldown_days": body.cooldownDays,
        "templates": {language.value: text for language, text in body.templates.items()},
        "default_language": body.defaultLanguage,
    }
    async with get_sessionmaker()() as session, session.begin():
        current = await session.get(HoldingReplySettings, user_id)
        # Switching on starts the clock: emails already in the inbox never get a holding reply.
        is_switching_on = body.enabled and not (current and current.enabled)
        enabled_at = datetime.now(timezone.utc) if is_switching_on else (current.enabled_at if current else None)
        statement = insert(HoldingReplySettings).values(user_id=user_id, enabled_at=enabled_at, **values)
        await session.execute(statement.on_conflict_do_update(
            index_elements=["user_id"], set_={**values, "enabled_at": enabled_at, "updated_at": datetime.now(timezone.utc)}))
    await audit("holding_reply_settings", f"user={user_id} enabled={body.enabled}")
    return body


@router.get("/holding-replies")
async def list_route(request: Request, limit: Annotated[int, Query(ge=1, le=MAX_LIST)] = 20) -> list[HoldingReplyView]:
    stmt = (select(HoldingReply, Message.subject).join(Message, Message.id == HoldingReply.message_id)
            .where(HoldingReply.user_id == _user_id(request))
            .order_by(HoldingReply.created_at.desc()).limit(limit))
    async with get_sessionmaker()() as session:
        rows = (await session.execute(stmt)).all()
    return [HoldingReplyView(
        id=str(reply.id), emailId=str(reply.message_id), recipient=reply.recipient_addr, language=reply.language,
        scheduledFor=reply.scheduled_for, sentAt=reply.sent_at, cancelledReason=reply.cancelled_reason,
        subject=subject or "",
    ) for reply, subject in rows]


@router.delete("/holding-replies/{reply_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_route(reply_id: UUID, request: Request) -> Response:
    """Cancel one still waiting. 404 for someone else's, 409 once sent or already cancelled."""
    user_id = _user_id(request)
    async with get_sessionmaker()() as session, session.begin():
        cancelled = await session.scalar(update(HoldingReply).where(
            HoldingReply.id == reply_id, HoldingReply.user_id == user_id, HoldingReply.sent_at.is_(None),
            HoldingReply.cancelled_reason.is_(None)).values(cancelled_reason=Refusal.CANCELLED_BY_USER)
            .returning(HoldingReply.id))
        exists = cancelled or await session.scalar(select(HoldingReply.id).where(
            HoldingReply.id == reply_id, HoldingReply.user_id == user_id))
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
    if not cancelled:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_sent_or_cancelled")
    await audit("holding_reply_cancelled", f"reply={reply_id} reason={Refusal.CANCELLED_BY_USER}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
