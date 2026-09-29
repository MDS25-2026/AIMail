"""Read-only aggregates for the admin console. Nothing here returns email content."""

import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import (
    AuditEvent,
    Count,
    FlaggedDraft,
    MailboxCounts,
    ModelHealth,
    Overview,
    PrivacyCounts,
)
from app.core.percentile import percentile
from app.db.models import AuditLog, MaskingStatus, Message

TOP_REASONS = 10
AUDIT_DETAIL_CHARS = 240
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# The listener's stable token first; the prose form only for rows written before it existed.
_WITHHELD = re.compile(r"withheld=(\d+)|(\d+) withheld locally")
DROP_ATTACHMENT_ACTION = "drop_attachment_text"
LEGACY_DROP_WORDING = "attachment text dropped"


def reason_category(reason: str) -> str:
    """"does not address: Send the invoice" becomes "does not address". The text after a colon can
    quote the email, and numbers make every reason unique; neither belongs in an aggregate."""
    return _NUMBER.sub("#", reason.split(":", 1)[0]).strip()


def _counted(condition: object) -> object:
    return func.count().filter(condition)


async def mailbox_counts(session: AsyncSession) -> MailboxCounts:
    """Every count in one round trip (COUNT ... FILTER), not one query each."""
    row = (await session.execute(select(
        func.count().label("total"),
        _counted(Message.masking_status == MaskingStatus.PENDING).label("masking_pending"),
        _counted(Message.masking_status == MaskingStatus.ABANDONED).label("masking_abandoned"),
        _counted(Message.generated_at.is_not(None)).label("generated"),
        _counted(Message.needs_human_review.is_(True) & Message.sent_at.is_(None)).label("awaiting_review"),
        _counted(Message.sent_at.is_not(None)).label("sent"),
        _counted(Message.read_at.is_(None)).label("unread"),
    ).select_from(Message))).one()
    return MailboxCounts(**row._mapping)


async def _audit_rows(session: AsyncSession, since: datetime) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.created_at >= since)
    return list((await session.scalars(stmt)).all())


def _is_drop(row: AuditLog) -> bool:
    return row.action == DROP_ATTACHMENT_ACTION or LEGACY_DROP_WORDING in (row.detail or "")


def privacy_counts(rows: list[AuditLog]) -> PrivacyCounts:
    def detail(row: AuditLog) -> str:
        return row.detail or ""

    return PrivacyCounts(
        quarantined=sum(1 for r in rows if r.action == "quarantine_message" and r.success),
        released=sum(1 for r in rows if r.action == "remask_message" and r.success),
        degraded_before_fix=sum(1 for r in rows if "presidio degraded" in detail(r)),
        attachment_text_dropped=sum(1 for r in rows if _is_drop(r)),
        pages_withheld=sum(int(m.group(1) or m.group(2)) for r in rows
                           if (m := _WITHHELD.search(detail(r)))),
        attachment_failures=sum(
            1 for r in rows
            if r.action in ("read_attachment", "ocr_attachment") and r.success is False
            and not _is_drop(r)
        ),
    )


def review_reasons(checks: list[dict]) -> list[Count]:
    counted = Counter(reason_category(reason) for c in checks for reason in c.get("review_reasons") or [])
    return [Count(label=label, count=n) for label, n in counted.most_common(TOP_REASONS)]


def model_health(checks: list[dict]) -> ModelHealth:
    drafts = [c.get("model_calls") or [] for c in checks if c.get("model_calls")]
    outcomes = Counter(call["outcome"] for calls in drafts for call in calls)
    return ModelHealth(
        drafts=len(drafts),
        attempts=sum(len(calls) for calls in drafts),
        outcomes=[Count(label=label, count=n) for label, n in outcomes.most_common()],
        drafts_using_fallback=sum(1 for calls in drafts if len({c["model"] for c in calls}) > 1),
        model_ms_p50=percentile([sum(c["ms"] for c in calls) for calls in drafts], 0.5),
        model_ms_p95=percentile([sum(c["ms"] for c in calls) for calls in drafts], 0.95),
    )


async def overview(session: AsyncSession, days: int) -> Overview:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Message.critic_checks).where(Message.generated_at >= since,
                                               Message.critic_checks.is_not(None))
    checks = [c for c in (await session.scalars(stmt)).all() if isinstance(c, dict)]
    return Overview(
        days=days,
        mailbox=await mailbox_counts(session),
        privacy=privacy_counts(await _audit_rows(session, since)),
        review_reasons=review_reasons(checks),
        models=model_health(checks),
    )


async def audit_events(session: AsyncSession, limit: int, only_failures: bool) -> list[AuditEvent]:
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if only_failures:
        stmt = stmt.where(AuditLog.success.is_(False))
    return [
        AuditEvent(created_at=row.created_at.isoformat(), action=row.action or "",
                   success=row.success, detail=(row.detail or "")[:AUDIT_DETAIL_CHARS])
        for row in (await session.scalars(stmt)).all()
    ]


async def flagged_drafts(session: AsyncSession, limit: int) -> list[FlaggedDraft]:
    stmt = (
        select(Message)
        .where(Message.needs_human_review.is_(True), Message.sent_at.is_(None))
        .order_by(Message.generated_at.desc())
        .limit(limit)
    )
    return [
        FlaggedDraft(
            id=str(m.id), subject=m.subject or "",
            generated_at=m.generated_at.isoformat() if m.generated_at else None,
            confidence=m.critic_confidence, attempts=m.critic_attempts,
            reasons=sorted({reason_category(r) for r in (m.critic_checks or {}).get("review_reasons") or []}),
        )
        for m in (await session.scalars(stmt)).all()
    ]
