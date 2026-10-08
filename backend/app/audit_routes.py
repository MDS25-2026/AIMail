"""The audit trail, as the signed-in user sees it (specs/features/sender-verification-and-audit.md).

Each user sees only their own rows; a script holding the shared token sees every row. Whether the
chain is intact is checked over the whole table first, because a gap or an edit anywhere breaks it.
"""

import json
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
from sqlalchemy import Row, text

from app.core.auth import principal_of
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
       c.is_valid
FROM audit_log a LEFT JOIN chain c ON c.id = a.id
"""
_ORDER = " ORDER BY a.created_at DESC, a.id DESC LIMIT :limit"


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
    fields: dict[str, AuditField]
    success: bool | None
    prevHash: str | None
    currentHash: str | None
    verification: Verification


class AuditTrailResponse(BaseModel):
    # Whole table, not just the rows shown: an edit or a deletion anywhere breaks the chain.
    isChainIntact: bool
    totalRecords: int
    verifiedRecords: int
    # The latest hash: record it somewhere outside the database to detect a rewrite of the whole chain.
    headHash: str | None
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
        fields=_fields(row.detail),
        success=row.success,
        prevHash=row.prev_hash,
        currentHash=row.current_hash,
        verification=_verification(row.is_valid),
    )


def _events_query(user_id: UUID | None) -> tuple[str, dict[str, object]]:
    """A person sees their own rows only; rows with no owner are system events, not theirs."""
    if user_id is None:
        return _EVENTS + _ORDER, {}
    return _EVENTS + " WHERE a.user_id = :uid" + _ORDER, {"uid": user_id}


@router.get("", response_model=AuditTrailResponse)
async def get_audit_trail(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=MAX_EVENTS)] = DEFAULT_EVENTS,
) -> AuditTrailResponse:
    principal = principal_of(request)
    # Never fall through to "every row": a person with no account yet owns nothing in the log.
    if not principal.is_service and principal.user_id is None:
        return AuditTrailResponse(isChainIntact=True, totalRecords=0, verifiedRecords=0,
                                  headHash=None, events=[])
    sql, params = _events_query(None if principal.is_service else principal.user_id)
    async with get_sessionmaker()() as session:
        summary = (await session.execute(_SUMMARY)).one()
        rows = (await session.execute(text(sql), {**params, "limit": limit})).all()
    events = [_event(row) for row in rows]
    return AuditTrailResponse(
        isChainIntact=summary.is_intact,
        totalRecords=len(events),
        verifiedRecords=sum(1 for event in events if event.verification == Verification.VERIFIED),
        headHash=summary.head,
        events=events,
    )
