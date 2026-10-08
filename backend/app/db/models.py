"""ORM models for the RAG policy-grounding tables.

The DDL source of truth is app/db/migrations/0001_rag_tables.sql; these models
mirror it for querying and inserts. See specs/context/db-schema.md.
"""

from datetime import date, datetime, time
from enum import StrEnum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    LargeBinary,
    SmallInteger,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import EMBEDDING_DIM, LOCAL_EMBEDDING_DIM
from app.db.base import Base


class DocType(StrEnum):
    POLICY = "policy"
    # A reply the user sent while writing-style learning was on (specs/features/writing-profile.md).
    SENT_REPLY = "sent_reply"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source: Mapped[str] = mapped_column(Text)
    # The owner's knowledge base (migration 0017); NULL is the original single mailbox's.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_profile.id"))
    title: Mapped[str | None] = mapped_column(Text)
    doc_type: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
    __tablename__ = "chunk"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("document.id", ondelete="CASCADE"))
    chunk_idx: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int | None]
    # 'metadata' is reserved on DeclarativeBase, so the attribute is 'meta'.
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    document: Mapped["Document"] = relationship(back_populates="chunks")
    embeddings: Mapped[list["Embedding"]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )


class Embedding(Base):
    __tablename__ = "embedding"

    # Append-only: a re-embed writes a new row, so there is no updated_at.
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("chunk.id", ondelete="CASCADE"))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))
    model_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunk: Mapped["Chunk"] = relationship(back_populates="embeddings")


class LocalEmbedding(Base):
    """Private mode's vectors (migration 0023); never compared with a Gemini vector."""

    __tablename__ = "local_embedding"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("chunk.id", ondelete="CASCADE"))
    embedding: Mapped[list[float]] = mapped_column(Vector(LOCAL_EMBEDDING_DIM))
    model_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Pipeline action trail. Lane A's Go listener writes ingestion rows (setup_watch,
    fetch_message, store_message); Lane B writes generation, refinement and send rows so the
    half of the pipeline after ingestion is auditable too. Columns mirror the listener's
    AuditLogEntry struct exactly — see 0002_messages.sql."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_profile.id", ondelete="SET NULL"))
    action: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    success: Mapped[bool | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set by the database trigger (migration 0024), never by the app.
    prev_hash: Mapped[str | None] = mapped_column(Text)
    current_hash: Mapped[str | None] = mapped_column(Text)
    chain_seq: Mapped[int | None] = mapped_column(BigInteger)


class AuthStatus(StrEnum):
    """The sender's domain check (SPF, DKIM, DMARC), read by the listener (migration 0024)."""

    PASS = "pass"
    SPOOF_DETECTED = "spoof_detected"
    # The owner looked at a flagged email and said the sender is real; drafting is allowed again.
    SENDER_CONFIRMED = "sender_confirmed"


class MaskingStatus(StrEnum):
    """#109: a pending row exists without content until the listener can mask it with NER."""

    COMPLETE = "complete"
    PENDING = "pending"
    # The listener gave up (deleted from Gmail, or never maskable): content is never stored.
    ABANDONED = "abandoned"


class Message(Base):
    """Ingested email. Lane A writes the top block via PostgREST; Lane B writes the priority block."""

    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The mailbox owner (migration 0007); filled for every row once per-user mailboxes land.
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("user_profile.id"))
    # Mailing-list, bulk, auto-submitted or no-reply mail (migration 0019); never auto-answered.
    is_automated: Mapped[bool] = mapped_column(default=False)
    # Sealed placeholder-to-value map (migration 0018, app/core/vault.py); never decoded here.
    pii_vault: Mapped[bytes | None] = mapped_column(LargeBinary)
    gmail_message_id: Mapped[str | None] = mapped_column(Text)
    from_addr: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    body_masked: Mapped[str | None] = mapped_column(Text)
    snippet_masked: Mapped[str | None] = mapped_column(Text)
    emails_masked: Mapped[int | None]
    phones_masked: Mapped[int | None]
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    importance: Mapped[int | None]
    importance_confidence: Mapped[float | None]
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    importance_model_version: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    category_confidence: Mapped[float | None]
    # Lane C generation, cached so opening an email doesn't regenerate every time.
    ai_summary: Mapped[str | None] = mapped_column(Text)
    draft_reply: Mapped[str | None] = mapped_column(Text)
    # Only while writing-style learning is on (migration 0020): the draft before the user's edits.
    draft_shown: Mapped[str | None] = mapped_column(Text)
    edit_ratio: Mapped[float | None]
    action_items: Mapped[list[str] | None] = mapped_column(JSONB)
    critic_confidence: Mapped[float | None]
    critic_attempts: Mapped[int | None]
    critic_checks: Mapped[dict | None] = mapped_column(JSONB)
    needs_human_review: Mapped[bool | None]
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Thread identity (migration 0009): Lane A writes the first three at ingest, the backend
    # writes sent_message_id after a reply goes out.
    thread_id: Mapped[str | None] = mapped_column(Text)
    rfc822_message_id: Mapped[str | None] = mapped_column(Text)
    thread_refs: Mapped[str | None] = mapped_column(Text)
    sent_message_id: Mapped[str | None] = mapped_column(Text)
    # The policy chunks the cached draft was grounded on (migration 0011).
    rag_sources: Mapped[list[dict] | None] = mapped_column(JSONB)
    masking_status: Mapped[str] = mapped_column(Text, server_default=MaskingStatus.COMPLETE)
    # Failed drafting attempts; the poller skips a message after MAX_GENERATION_ATTEMPTS (0014).
    generation_attempts: Mapped[int] = mapped_column(server_default="0")
    # Where an approved reply goes when the sender set Reply-To; shown to the approver (0014).
    reply_to: Mapped[str | None] = mapped_column(Text)

    @property
    def is_masked(self) -> bool:
        """Content exists and was masked with NER. Nothing reads or drafts from a row that is not."""
        return self.masking_status == MaskingStatus.COMPLETE
    auth_status: Mapped[str | None] = mapped_column(Text, default=AuthStatus.PASS)

    @property
    def is_spoofed(self) -> bool:
        """Failed SPF, DKIM or DMARC and not confirmed by the owner: never drafted or answered."""
        return self.auth_status == AuthStatus.SPOOF_DETECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    """The mailbox owner. Keyed by email because that is the identifier every lane already shares."""

    __tablename__ = "user_profile"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPreferences(Base):
    """Defaults reproduce today's behaviour, so an unconfigured user sees no change."""

    __tablename__ = "user_preferences"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    priority_bias: Mapped[int]
    default_sort: Mapped[str] = mapped_column(Text)
    default_tone: Mapped[str] = mapped_column(Text)
    # Private mode (migration 0022): "gemini" or "local".
    draft_provider: Mapped[str] = mapped_column(Text, default="gemini")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SenderRule(Base):
    """Exact-sender override. A lookup — never prompt input."""

    __tablename__ = "sender_rule"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    from_addr: Mapped[str] = mapped_column(Text, primary_key=True)
    priority: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KeywordRule(Base):
    """Topic override, same shape as SenderRule."""

    __tablename__ = "keyword_rule"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    keyword: Mapped[str] = mapped_column(Text, primary_key=True)
    priority: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MailboxConnection(Base):
    """A user's connected Gmail (migration 0016). The refresh token is only ever stored sealed."""

    __tablename__ = "mailbox_connection"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    provider: Mapped[str] = mapped_column(Text, default="gmail")
    email: Mapped[str] = mapped_column(Text, unique=True)
    refresh_token_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    history_id: Mapped[int | None] = mapped_column(BigInteger)
    watch_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Google refused the stored token (migration 0021); signing in again clears it.
    needs_reconnect: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HoldingReplySettings(Base):
    """One user's holding reply (migration 0019, specs/features/holding-reply.md)."""

    __tablename__ = "holding_reply_settings"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(default=False)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_when: Mapped[str] = mapped_column(Text, default="outside_hours")
    work_days: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), default=lambda: [1, 2, 3, 4, 5])
    work_start: Mapped[time] = mapped_column(Time, default=time(9))
    work_end: Mapped[time] = mapped_column(Time, default=time(18))
    timezone: Mapped[str] = mapped_column(Text, default="Asia/Kuala_Lumpur")
    leave_from: Mapped[date | None] = mapped_column(Date)
    leave_until: Mapped[date | None] = mapped_column(Date)
    audience: Mapped[str] = mapped_column(Text, default="correspondents")
    scope: Mapped[str] = mapped_column(Text, default="needs_reply")
    cooldown_days: Mapped[int] = mapped_column(SmallInteger, default=4)
    templates: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_language: Mapped[str] = mapped_column(Text, default="en")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HoldingReply(Base):
    """One scheduled holding reply: sent, cancelled with a reason, or still waiting."""

    __tablename__ = "holding_reply"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"))
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id"), unique=True)
    recipient_addr: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    sent_message_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WritingStyle(Base):
    """One user's writing style (migration 0020, specs/features/writing-profile.md). Masked text only."""

    __tablename__ = "writing_style"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="")
    learning_enabled: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StyleExample(Base):
    __tablename__ = "style_example"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"))
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StyleHabit(Base):
    __tablename__ = "style_habit"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("user_profile.id"))
    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    evidence: Mapped[int] = mapped_column(SmallInteger)
    out_of: Mapped[int] = mapped_column(SmallInteger)
    suppressed: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
