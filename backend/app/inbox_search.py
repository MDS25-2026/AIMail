"""Natural language inbox search and thread Q&A assistant (Issue #144).

Implements hybrid retrieval (PostgreSQL tsvector + pgvector semantic similarity merged via RRF)
and dual-grounded Gemini answer synthesis across masked messages and policy documents.
"""

import logging
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError

import model_gateway
from app.core.ownership import Scope
from app.core.providers import Provider
from app.core.typed_text import mask_typed_text
from app.db.models import Chunk, Document, Message
from app.db.session import get_sessionmaker
from app.rag.retrieve import ContextChunk
from app.rag.retrieve import search as search_policy_documents
from model_runtime import ModelError

logger = logging.getLogger(__name__)

PURPOSE_SEARCH = "inbox_search"
PURPOSE_QA = "inbox_qa"
PURPOSE_REFORMULATE = "inbox_reformulate"
RRF_K = 60


class SourceType(StrEnum):
    EMAIL = "email"
    DOCUMENT = "document"


class SearchSource(BaseModel):
    source_type: SourceType
    id: str
    title: str
    subtitle: str
    snippet: str
    received_at: str | None = None


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class InboxSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list)
    k_emails: int = Field(default=5, ge=1, le=20)
    k_docs: int = Field(default=3, ge=1, le=10)


class InboxSearchResponse(BaseModel):
    answer: str
    sources: list[SearchSource]
    sender_vault: dict[str, str] = Field(default_factory=dict)


async def contextualize_query(query: str, history: list[ChatMessage], provider: Provider) -> str:
    """Resolve pronouns and conversational context into a self-contained search query."""
    if not history:
        return query

    # Take the last 6 messages (3 turns) to keep reformulation fast and focused
    recent_history = history[-6:]
    formatted_turns = "\n".join(f"{m.role.capitalize()}: {m.content}" for m in recent_history)

    prompt = f"""Given the following conversation history and a follow-up question, rewrite the follow-up question into a standalone search query.
Resolve all pronouns (e.g. "it", "that", "she", "they", "the second one") using the conversation history.
Keep it under 30 words. Output only the rewritten query with no explanations.

Conversation:
{formatted_turns}

Follow-up question: {query}
Standalone query:"""

    try:
        rewritten = await model_gateway.generate(
            prompt,
            provider=provider,
            purpose=PURPOSE_REFORMULATE,
            max_output_tokens=64,
        )
        if isinstance(rewritten, str) and rewritten.strip():
            return rewritten.strip()
    except ModelError as exc:
        logger.warning("Query contextualization failed, falling back to raw query: %s", exc)

    return query


async def search_messages_hybrid(
    search_query: str,
    k: int,
    *,
    scope: Scope,
    provider: Provider,
) -> list[Message]:
    """Retrieve top-k messages using Reciprocal Rank Fusion of tsvector and pgvector results."""
    query_vector = await model_gateway.embed_query(
        search_query,
        provider=provider,
        purpose=PURPOSE_SEARCH,
    )

    async with get_sessionmaker()() as session:
        # 1. Full-Text Search (Keyword Rank)
        fts_rows: list[Message] = []
        try:
            fts_stmt = (
                select(Message)
                .where(
                    Message.search_vector.op("@@")(func.websearch_to_tsquery("english", search_query)),
                    scope.where(Message.user_id),
                )
                .order_by(
                    func.ts_rank_cd(
                        Message.search_vector,
                        func.websearch_to_tsquery("english", search_query),
                    ).desc()
                )
                .limit(20)
            )
            fts_rows = (await session.scalars(fts_stmt)).all()
        except SQLAlchemyError as exc:
            logger.debug("websearch_to_tsquery produced no result or error: %s, trying plainto_tsquery", exc)
            try:
                plain_stmt = (
                    select(Message)
                    .where(
                        Message.search_vector.op("@@")(func.plainto_tsquery("english", search_query)),
                        scope.where(Message.user_id),
                    )
                    .order_by(
                        func.ts_rank_cd(
                            Message.search_vector,
                            func.plainto_tsquery("english", search_query),
                        ).desc()
                    )
                    .limit(20)
                )
                fts_rows = (await session.scalars(plain_stmt)).all()
            except SQLAlchemyError as inner_exc:
                logger.warning("FTS search fallback failed: %s", inner_exc)

        # Check if query matches a sender name locally in PostgreSQL (e.g. "Bryan")
        sender_rows: list[Message] = []
        cleaned_words = [
            w
            for w in re.findall(r"\b[A-Za-z]{3,}\b", search_query)
            if w.lower()
            not in {
                "any",
                "emails",
                "email",
                "from",
                "with",
                "about",
                "what",
                "when",
                "show",
                "find",
                "have",
                "received",
                "regarding",
            }
        ]
        if cleaned_words:
            try:
                conditions = [Message.from_addr.ilike(f"%{w}%") for w in cleaned_words]
                sender_stmt = (
                    select(Message)
                    .where(
                        or_(*conditions),
                        scope.where(Message.user_id),
                    )
                    .order_by(Message.received_at.desc())
                    .limit(10)
                )
                sender_rows = (await session.scalars(sender_stmt)).all()
            except SQLAlchemyError as exc:
                logger.debug("Sender search query failed: %s", exc)

        # 2. Vector Search (Cosine Similarity with 55% threshold / distance <= 0.45)
        vec_rows: list[Message] = []
        if query_vector:
            try:
                distance = Message.embedding.cosine_distance(query_vector)
                vec_stmt = (
                    select(Message)
                    .where(
                        Message.embedding.is_not(None),
                        scope.where(Message.user_id),
                        distance <= 0.45,  # Filter out low-similarity noise
                    )
                    .order_by(distance)
                    .limit(20)
                )
                vec_rows = (await session.scalars(vec_stmt)).all()
            except SQLAlchemyError as exc:
                logger.warning("Vector search failed: %s", exc)

        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores: dict[UUID, float] = {}
        message_map: dict[UUID, Message] = {}

        for rank, msg in enumerate(sender_rows):
            message_map[msg.id] = msg
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (2.0 / (RRF_K + rank + 1))

        for rank, msg in enumerate(fts_rows):
            message_map[msg.id] = msg
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (1.0 / (RRF_K + rank + 1))

        for rank, msg in enumerate(vec_rows):
            message_map[msg.id] = msg
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (1.0 / (RRF_K + rank + 1))

        if not rrf_scores:
            return []

        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)[:k]
        return [message_map[mid] for mid in sorted_ids]


def format_email_snippet(msg: Message) -> str:
    """Produce a concise excerpt of an email for context and citation display."""
    body = (msg.body_masked or msg.snippet_masked or "").strip()
    clean = " ".join(body.split())
    if len(clean) > 280:
        return clean[:277] + "..."
    return clean or "No body content"


def format_received_date(dt: datetime | None) -> str:
    if not dt:
        return "Unknown date"
    return dt.strftime("%d %b %Y, %I:%M %p")


async def execute_inbox_search(
    request: InboxSearchRequest,
    *,
    scope: Scope,
    provider: Provider,
) -> InboxSearchResponse:
    """Execute dual hybrid retrieval across emails and policy docs, synthesizing a grounded answer."""
    sanitized_query = mask_typed_text(request.query)

    # Contextualize query with conversational history
    effective_query = await contextualize_query(sanitized_query, request.history, provider)

    # 1. Retrieve relevant inbox emails (strictly relevance-filtered)
    matched_emails = await search_messages_hybrid(
        effective_query,
        request.k_emails,
        scope=scope,
        provider=provider,
    )

    # 2. Retrieve relevant policy documents (Knowledge base)
    matched_docs: list[ContextChunk] = []
    try:
        raw_docs = await search_policy_documents(
            effective_query,
            request.k_docs,
            scope=scope,
            provider=provider,
        )
        # Relevance floor: only keep chunks scoring >= 0.55 similarity
        matched_docs = [d for d in raw_docs if d.get("similarity_score", 0.0) >= 0.55]
    except (SQLAlchemyError, ModelError) as exc:
        logger.warning("Knowledge base retrieval failed during inbox search: %s", exc)

    # Resolve document_id for chunks to enable grouping and deep-linking
    chunk_ids = [doc["chunk_id"] for doc in matched_docs]
    chunk_docs_map: dict[UUID, tuple[UUID, str]] = {}
    if chunk_ids:
        try:
            async with get_sessionmaker()() as session:
                c_rows = (
                    await session.execute(
                        select(Chunk.id, Chunk.document_id, Document.title)
                        .join(Document, Document.id == Chunk.document_id)
                        .where(Chunk.id.in_(chunk_ids))
                    )
                ).all()
                for c_id, d_id, d_title in c_rows:
                    chunk_docs_map[c_id] = (d_id, d_title or "Policy Document")
        except SQLAlchemyError as exc:
            logger.debug("Failed to resolve document titles for chunks: %s", exc)

    # 3. Assemble and Aggregate Sources
    sources: list[SearchSource] = []

    # Group emails by thread
    threads_map: dict[str, list[Message]] = {}
    for msg in matched_emails:
        t_id = msg.thread_id or str(msg.id)
        threads_map.setdefault(t_id, []).append(msg)

    for t_id, thread_msgs in threads_map.items():
        newest = thread_msgs[0]
        date_str = format_received_date(newest.received_at)
        sender_disp = newest.from_addr or "Unknown sender"
        count = len(thread_msgs)
        subtitle = f"{sender_disp} · {date_str}" + (f" · {count} messages" if count > 1 else "")
        sources.append(
            SearchSource(
                source_type=SourceType.EMAIL,
                id=str(newest.id),
                title=newest.subject or "(No Subject)",
                subtitle=subtitle,
                snippet=format_email_snippet(newest),
                received_at=newest.received_at.isoformat() if newest.received_at else None,
            )
        )

    # Group policy chunks by Document ID
    docs_by_id: dict[UUID, list[ContextChunk]] = {}
    for doc in matched_docs:
        info = chunk_docs_map.get(doc["chunk_id"])
        doc_id = info[0] if info else doc["chunk_id"]
        docs_by_id.setdefault(doc_id, []).append(doc)

    for doc_id, chunk_list in docs_by_id.items():
        best_chunk = max(chunk_list, key=lambda c: c["similarity_score"])
        doc_title = chunk_docs_map.get(
            best_chunk["chunk_id"],
            (doc_id, best_chunk["source_title"].split(" · ")[0]),
        )[1]
        count = len(chunk_list)
        top_score = int(best_chunk["similarity_score"] * 100)
        subtitle = f"Knowledge Base · {count} matching section{'s' if count > 1 else ''} ({top_score}% match)"
        sources.append(
            SearchSource(
                source_type=SourceType.DOCUMENT,
                id=str(doc_id),
                title=doc_title,
                subtitle=subtitle,
                snippet=best_chunk["content"][:280] + ("..." if len(best_chunk["content"]) > 280 else ""),
                received_at=None,
            )
        )

    # If no sources found at all
    if not sources:
        return InboxSearchResponse(
            answer="I searched your inbox and knowledge base but could not find any relevant emails or documents regarding your query.",
            sources=[],
            sender_vault={},
        )

    # 4. Construct grounded synthesis prompt with Strict Zero-Knowledge Sender Anonymization
    email_blocks: list[str] = []
    sender_vault: dict[str, str] = {}
    for idx, msg in enumerate(matched_emails, 1):
        sender_placeholder = f"[SENDER_{idx}]"
        if msg.from_addr:
            sender_vault[sender_placeholder] = msg.from_addr

        # NEVER send raw msg.from_addr to Gemini. Use sender_placeholder to preserve privacy.
        email_blocks.append(
            f"[Email {idx}]\n"
            f"Subject: {msg.subject or '(No subject)'}\n"
            f"From: {sender_placeholder}\n"
            f"Date: {format_received_date(msg.received_at)}\n"
            f"Content: {(msg.body_masked or msg.snippet_masked or '').strip()[:1500]}"
        )

    doc_blocks: list[str] = []
    for idx, doc in enumerate(matched_docs, 1):
        doc_blocks.append(
            f"[Document {idx} - {doc['source_title']}]\n"
            f"{doc['content'][:1500]}"
        )

    emails_section = "\n\n".join(email_blocks) if email_blocks else "None found."
    docs_section = "\n\n".join(doc_blocks) if doc_blocks else "None found."

    history_text = ""
    if request.history:
        history_lines = [f"{m.role.capitalize()}: {m.content}" for m in request.history[-6:]]
        history_text = "Prior conversation:\n" + "\n".join(history_lines) + "\n\n"

    synthesis_prompt = f"""You are AImail's intelligent inbox and knowledge assistant.
Answer the user's question clearly, professionally, and concisely based strictly on the provided retrieved emails and documents.

Rules:
1. Ground your answer completely in the retrieved sources. Do not hallucinate or speculate.
2. Specifically cite relevant email subjects, senders, dates, or document titles when presenting facts.
3. If the retrieved sources do not contain sufficient information to answer the question, clearly state what is known and what cannot be answered from the correspondence.
4. Keep the tone enterprise-ready, polite, and helpful. Strictly do not use emojis.
5. Structure your response clearly using bullet points and short paragraphs. Bold key entities, dates, or metrics (e.g. **October 8, 2026**).

{history_text}Retrieved Inbox Emails:
{emails_section}

Retrieved Company Knowledge Documents:
{docs_section}

User Question: {sanitized_query}
Helpful Grounded Answer:"""

    try:
        answer = await model_gateway.generate(
            synthesis_prompt,
            provider=provider,
            purpose=PURPOSE_QA,
            max_output_tokens=512,
        )
        if isinstance(answer, str) and answer.strip():
            answer_text = answer.strip()
        else:
            answer_text = "I could not synthesize an answer from the retrieved sources."
    except ModelError as exc:
        logger.error("Synthesis generation failed: %s", exc)
        answer_text = "I encountered an error communicating with the AI model while analyzing your retrieved emails."

    return InboxSearchResponse(
        answer=answer_text,
        sources=sources,
        sender_vault=sender_vault,
    )
