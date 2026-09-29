"""Admin response shapes. Aggregates, ids, masked subjects: never a body, never a draft."""

from pydantic import BaseModel


class AdminIdentity(BaseModel):
    email: str


class SignInRequest(BaseModel):
    email: str
    password: str


class MailboxCounts(BaseModel):
    total: int
    masking_pending: int
    masking_abandoned: int
    generated: int
    awaiting_review: int
    sent: int
    unread: int


class PrivacyCounts(BaseModel):
    quarantined: int
    released: int
    degraded_before_fix: int
    attachment_text_dropped: int
    pages_withheld: int
    attachment_failures: int


class Count(BaseModel):
    label: str
    count: int


class ModelHealth(BaseModel):
    drafts: int
    attempts: int
    outcomes: list[Count]
    drafts_using_fallback: int
    model_ms_p50: int | None
    model_ms_p95: int | None


class Overview(BaseModel):
    days: int
    mailbox: MailboxCounts
    privacy: PrivacyCounts
    review_reasons: list[Count]
    models: ModelHealth


class AuditEvent(BaseModel):
    created_at: str
    action: str
    success: bool | None
    detail: str


class FlaggedDraft(BaseModel):
    id: str
    subject: str
    generated_at: str | None
    confidence: float | None
    attempts: int | None
    reasons: list[str]
