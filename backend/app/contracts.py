"""Cross-lane data contracts (the Seams). Single source of truth — both lanes import these,
never hand-copy the shapes. Mirrored in human-readable form in specs/context/api-contracts.md.

Provisional. Rule of thumb: adding a field is cheap and safe; changing or removing one is a
contract break — flag it to the affected lane (Lane C / Lane D) before merging.
"""

from datetime import datetime
from typing import Literal, TypedDict
from uuid import UUID

from pydantic import BaseModel


class ContextChunk(TypedDict):
    """Seam 2 — Lane B retrieval -> Lane C generation (in-process).

    Returned by `retrieve(masked_email, k)`; Lane C builds its prompt from these.
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


class Source(BaseModel):
    label: str


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


_PRIORITY_LABELS: dict[int, Literal["low", "medium", "high"]] = {0: "low", 1: "medium", 2: "high"}


def priority_label(importance: int | None) -> Literal["low", "medium", "high"]:
    """Map the classifier's importance value (0/1/2) to the dashboard's lowercase priority."""
    return _PRIORITY_LABELS.get(importance, "medium")
