"""Cross-lane data contracts (the Seams). Single source of truth — both lanes import these,
never hand-copy the shapes. Mirrored in human-readable form in specs/context/api-contracts.md.

Provisional. Rule of thumb: adding a field is cheap and safe; changing or removing one is a
contract break — flag it to the affected lane (Lane C / Lane D) before merging.
"""

from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models import AuthStatus


class ContextChunk(TypedDict):
    """Seam 2 — Lane B retrieval -> Lane C generation (in-process).

    Returned by `retrieve(masked_email, k, scope=...)`; Lane C builds its prompt from these.
    """

    chunk_id: UUID
    content: str
    similarity_score: float  # cosine, 0..1
    source_title: str


class EmailPriority(BaseModel):
    """Lane B classifier -> Lane D dashboard (per-email priority for display/sorting).

    `importance` is the trained model's output; `priority_score` is the composite (importance +
    deadline recency) computed at request time so it is never stale.
    """

    importance: Literal["LOW", "MEDIUM", "HIGH"]
    confidence: float  # 0..1
    deadline_at: datetime | None
    priority_score: float  # 0..1
    model_version: str


class ThreadMessage(BaseModel):
    sender: str
    snippet: str
    # A reply the mailbox owner sent from AIMail, shown under the email it answered.
    isOwnReply: bool = False
    # The full masked body and when it arrived (or, for the owner's reply, was sent): the
    # conversation view expands earlier messages in place (specs/features/conversation-view.md).
    body: str = ""
    timestamp: str | None = None


class Source(BaseModel):
    """A policy passage the draft was grounded on. `excerpt` is the passage as the model saw it."""

    label: str
    chunkId: str | None = None
    excerpt: str = ""
    score: float | None = None


class MeasureView(BaseModel):
    value: float
    unit: str


class QuantityView(BaseModel):
    """A quantity in the body, in both unit systems. The dashboard shows whichever the reader
    prefers; the side matching `system` is the figure exactly as the sender wrote it."""

    text: str
    system: Literal["metric", "imperial"]
    metric: MeasureView
    imperial: MeasureView


class Detail(BaseModel):
    """A personal detail the AI saw only as its placeholder (restorable masking). Owner only."""

    placeholder: str  # "[PERSON_1]"
    value: str
    kind: str  # "PERSON", "PHONE", ...


class DashboardEmail(BaseModel):
    """The joined email view the Lane D dashboard renders (matches Han's `Email` type).

    Fields are camelCase to match the frontend. Lane A fills sender/subject/preview/timestamp/
    piiMasked, Lane B fills priority, Lane C fills aiSummary/actionItems/draftReply/criticConfidence.
    """

    id: str
    sender: str
    subject: str
    preview: str  # short snippet for the inbox list
    body: str  # full masked email body for the detail view
    timestamp: str  # ISO 8601
    authStatus: AuthStatus  # the sender's SPF/DKIM/DMARC check, or the owner's confirmation
    priority: Literal["high", "medium", "low"]
    threadContext: list[ThreadMessage]
    aiSummary: str
    actionItems: list[str]
    draftReply: str
    tone: Literal["professional", "casual"]
    sources: list[Source]
    piiMasked: bool
    criticConfidence: float
    sentAt: str | None = None  # ISO 8601 when the approved reply was sent, else null
    isRead: bool = False  # opened at least once; unread is the default for anything new
    quantities: list[QuantityView] = []  # from the normalisation layer, computed at read
    # "pending" while the listener holds the content back because NER masking was unavailable,
    # "abandoned" once it gave up (#109). Either way subject, body and preview are empty.
    masking: Literal["complete", "pending", "abandoned"] = "complete"
    # Where an approved reply goes when the sender set a Reply-To; null means it goes to `sender`.
    replyTo: str | None = None
    # The Gmail thread, so the dashboard can show one inbox row per conversation.
    threadId: str | None = None
    # The real details behind this email's, its thread's and its draft's placeholders. Detail
    # responses only; empty on the list and for emails stored before restorable masking.
    details: list[Detail] = Field(default_factory=list)


_PRIORITY_LABELS: dict[int, Literal["low", "medium", "high"]] = {0: "low", 1: "medium", 2: "high"}


def priority_label(importance: int | None) -> Literal["low", "medium", "high"]:
    """Map the classifier's importance value (0/1/2) to the dashboard's lowercase priority."""
    return _PRIORITY_LABELS.get(importance, "medium")
