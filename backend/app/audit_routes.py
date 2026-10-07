"""Audit log routes: user-facing tamper-evident audit ledger (#148 / PDPA)."""

from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.core.auth import principal_of
from app.db.session import get_sessionmaker

router = APIRouter(prefix="/audit")


from sqlalchemy import text


class AuditEventOut(BaseModel):
    id: str
    created_at: str
    action: str
    detail: str
    success: bool | None
    prev_hash: str | None
    current_hash: str | None
    user_id: str | None
    is_verified: bool | None = None


class AuditTrailResponse(BaseModel):
    is_chain_intact: bool
    total_records: int
    verified_records: int
    events: list[AuditEventOut]


@router.get("", response_model=AuditTrailResponse)
async def get_audit_trail(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditTrailResponse:
    """Returns the tamper-evident audit ledger with cryptographic SHA-256 chain verification."""
    principal = principal_of(request)
    uid = principal.user_id

    # Compute row fields and verify SHA-256 digest mathematically in PostgreSQL
    sql = """
    SELECT 
        id,
        created_at,
        action,
        detail,
        success,
        prev_hash,
        current_hash,
        user_id,
        CASE 
            WHEN current_hash IS NULL THEN NULL
            ELSE current_hash = encode(digest(
                COALESCE(prev_hash, '0000000000000000000000000000000000000000000000000000000000000000') || 
                COALESCE(action, '') || 
                COALESCE(detail, '') || 
                COALESCE(success::text, 'false') || 
                COALESCE(user_id::text, '') || 
                extract(epoch from created_at)::text,
                'sha256'
            ), 'hex')
        END AS is_valid
    FROM audit_log
    """
    params: dict = {"limit": limit}
    if uid is not None and not principal.is_service:
        sql += " WHERE user_id = :uid OR user_id IS NULL"
        params["uid"] = uid

    sql += " ORDER BY created_at DESC, id DESC LIMIT :limit"

    async with get_sessionmaker()() as session:
        result = await session.execute(text(sql), params)
        rows = result.fetchall()

    events_out: list[AuditEventOut] = []
    verified_count = 0
    all_intact = True

    for row in rows:
        (
            id_,
            created_at,
            action,
            detail,
            success,
            prev_hash,
            current_hash,
            row_user_id,
            is_valid,
        ) = row

        is_verified = bool(is_valid) if is_valid is not None else None
        if is_valid is False:
            all_intact = False

        events_out.append(
            AuditEventOut(
                id=str(id_),
                created_at=created_at.isoformat() if created_at else "",
                action=action or "unspecified",
                detail=detail or "",
                success=success,
                prev_hash=prev_hash,
                current_hash=current_hash,
                user_id=str(row_user_id) if row_user_id else None,
                is_verified=is_verified,
            )
        )
        if current_hash is not None and is_valid is True:
            verified_count += 1

    return AuditTrailResponse(
        is_chain_intact=all_intact and (verified_count > 0 or len(rows) == 0),
        total_records=len(rows),
        verified_records=verified_count,
        events=events_out,
    )
