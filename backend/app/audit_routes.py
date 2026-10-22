"""The audit trail, for admins (specs/features/admin-only-pages.md, sender-verification-and-audit.md).

An admin, or a script holding the shared token, sees everyone's rows, each with its person and group;
anyone else is told the page does not exist. Whether the chain is intact is checked over the whole table
first, because a gap or an edit anywhere breaks it.
"""

import json
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import Row, text

from app.audit_groups import ActionGroup, actions_in, group_of, known_actions
from app.core.auth import principal_of
from app.core.errors import DomainError, ErrorCode
from app.db.session import get_sessionmaker

router = APIRouter(prefix="/audit")

MAX_EVENTS = 100
DEFAULT_EVENTS = 50
GENESIS_HASH = "0" * 64

# A row is verified when its hash matches its own fields and it follows the row before it without a
# gap. Rows written before migration 0024 have no chain_seq and are reported as unverified (NULL).
_CHAIN = f"""
WITH chain AS (
    SELECT id,
           current_hash = audit_row_hash(prev_hash, chain_seq, action, detail, success, user_id, created_at)
           AND prev_hash = COALESCE(lag(current_hash) OVER w, '{GENESIS_HASH}')
           AND chain_seq = COALESCE(lag(chain_seq) OVER w, 0) + 1 AS is_valid
    FROM audit_log
    WHERE chain_seq IS NOT NULL
    WINDOW w AS (ORDER BY chain_seq)
)
"""

_SUMMARY = text(_CHAIN + """
SELECT COALESCE(bool_and(is_valid), true) AS is_intact, count(*) AS chained,
       (SELECT current_hash FROM audit_log WHERE chain_seq IS NOT NULL ORDER BY chain_seq DESC LIMIT 1) AS head
FROM chain
""")

_EVENTS = _CHAIN + """
SELECT a.id, a.created_at, a.action, a.detail, a.success, a.prev_hash, a.current_hash, a.user_id,
       u.email AS user_email, c.is_valid, count(*) OVER () AS full_count,
       count(*) FILTER (WHERE a.success IS FALSE) OVER () AS failed_count
FROM audit_log a LEFT JOIN chain c ON c.id = a.id LEFT JOIN user_profile u ON u.id = a.user_id
"""
_ORDER = " ORDER BY a.created_at DESC, a.id DESC LIMIT :limit"
# Everyone an admin can filter by; the team is far below this.
MAX_PEOPLE = 200
_PEOPLE = text("SELECT id, email FROM user_profile ORDER BY email LIMIT :limit")


class AuditWindow(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


_WINDOW_LENGTH = {AuditWindow.DAY: timedelta(days=1), AuditWindow.WEEK: timedelta(days=7),
                  AuditWindow.MONTH: timedelta(days=30)}


class Verification(StrEnum):
    VERIFIED = "verified"
    TAMPERED = "tampered"
    # Written before the chain existed (no chain_seq): nothing to check it against. Never shown as verified.
    UNVERIFIABLE = "unverifiable"


AuditField = str | int | float | bool | None
# Rows written before 2026-10-08 hold prose; it is shown as text, never parsed.
PROSE_FIELD = "text"


class AuditEventOut(BaseModel):
    id: str
    createdAt: str
    action: str
    group: ActionGroup
    # Whose action, for an admin; None for a system event or a deleted account.
    userEmail: str | None = None
    fields: dict[str, AuditField]
    success: bool | None
    prevHash: str | None
    currentHash: str | None
    verification: Verification


class AuditPerson(BaseModel):
    id: str
    email: str


class AuditTrailResponse(BaseModel):
    # Whole table, not just the rows shown: an edit or a deletion anywhere breaks the chain.
    isChainIntact: bool
    totalRecords: int
    verifiedRecords: int
    # The latest hash: record it somewhere outside the database to detect a rewrite of the whole chain.
    headHash: str | None
    # Failures among the records the filters match, so the summary line reads "3 failures".
    failedRecords: int = 0
    people: list[AuditPerson] = []
    events: list[AuditEventOut]


def _verification(is_valid: bool | None) -> Verification:
    if is_valid is None:
        return Verification.UNVERIFIABLE
    return Verification.VERIFIED if is_valid else Verification.TAMPERED


def _fields(detail: str | None) -> dict[str, AuditField]:
    try:
        parsed = json.loads(detail or "")
    except ValueError:
        return {PROSE_FIELD: detail or ""}
    return parsed if isinstance(parsed, dict) else {PROSE_FIELD: detail or ""}


def _event(row: Row) -> AuditEventOut:
    return AuditEventOut(
        id=str(row.id),
        createdAt=row.created_at.isoformat() if row.created_at else "",
        action=row.action or "unspecified",
        group=group_of(row.action or ""),
        userEmail=row.user_email,
        fields=_fields(row.detail),
        success=row.success,
        prevHash=row.prev_hash,
        currentHash=row.current_hash,
        verification=_verification(row.is_valid),
    )


def _events_query(group: ActionGroup | None, person: UUID | None, is_failures_only: bool,
                  window: AuditWindow) -> tuple[str, dict[str, object]]:
    """The filters as SQL conditions with bound values; nothing the caller sends is pasted into the text."""
    conditions: list[str] = []
    params: dict[str, object] = {}
    if group is ActionGroup.OTHER:
        conditions.append("NOT (a.action = ANY(:known))")
        params["known"] = known_actions()
    elif group is not None:
        conditions.append("a.action = ANY(:actions)")
        params["actions"] = actions_in(group)
    if person is not None:
        conditions.append("a.user_id = :person")
        params["person"] = person
    if is_failures_only:
        conditions.append("a.success IS FALSE")
    if window is not AuditWindow.ALL:
        # The cutoff as a time, not now() minus a bound interval, which Postgres cannot type.
        conditions.append("a.created_at >= :since")
        params["since"] = datetime.now(timezone.utc) - _WINDOW_LENGTH[window]
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    return _EVENTS + where + _ORDER, params


@router.get("", response_model=AuditTrailResponse)
async def get_audit_trail(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=MAX_EVENTS)] = DEFAULT_EVENTS,
    group: ActionGroup | None = None,
    person: UUID | None = None,
    failures_only: bool = False,
    window: AuditWindow = AuditWindow.ALL,
) -> AuditTrailResponse:
    principal = principal_of(request)
    # Not "forbidden": to anyone but an admin the page does not exist, as the dashboard shows it.
    if not (principal.is_service or principal.is_admin):
        raise DomainError(ErrorCode.NOT_FOUND)
    sql, params = _events_query(group, person, failures_only, window)
    async with get_sessionmaker()() as session:
        summary = (await session.execute(_SUMMARY)).one()
        rows = (await session.execute(text(sql), {**params, "limit": limit})).all()
        people = (await session.execute(_PEOPLE, {"limit": MAX_PEOPLE})).all()
    events = [_event(row) for row in rows]
    return AuditTrailResponse(
        isChainIntact=summary.is_intact,
        totalRecords=int(rows[0].full_count) if rows else 0,
        verifiedRecords=sum(1 for event in events if event.verification == Verification.VERIFIED),
        headHash=summary.head,
        failedRecords=int(rows[0].failed_count) if rows else 0,
        people=[AuditPerson(id=str(row.id), email=row.email) for row in people],
        events=events,
    )
