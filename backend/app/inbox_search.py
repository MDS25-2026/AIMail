"""Natural language inbox search and thread Q&A assistant (Issue #144).

Implements hybrid retrieval (PostgreSQL tsvector + pgvector semantic similarity merged via RRF)
and dual-grounded Gemini answer synthesis across masked messages and policy documents,
with local AES-GCM vault PII restoration, sender query grounding, and universal source pruning.
"""

import logging
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.exc import SQLAlchemyError

import model_gateway
from app.core.ownership import Scope
from app.core.providers import Provider
from app.core.typed_text import mask_typed_text
from app.core.vault import ThreadMap, VaultUnavailableError, open_vault
from app.db.models import Chunk, Document, Message
from app.db.session import get_sessionmaker
from app.private_mode import not_private
from app.rag.retrieve import ContextChunk
from app.rag.retrieve import search as search_policy_documents
from model_runtime import ModelError

logger = logging.getLogger(__name__)

PURPOSE_SEARCH = "inbox_search"
PURPOSE_QA = "inbox_qa"
PURPOSE_REFORMULATE = "inbox_reformulate"
PURPOSE_ROUTE = "inbox_route"
RRF_K = 60

QUESTION_STOP_WORDS = frozenset({
    "tell", "me", "about", "any", "emails", "email", "from", "with", "what", "when",
    "where", "why", "how", "show", "find", "have", "received", "regarding", "the",
    "a", "an", "is", "was", "are", "were", "did", "does", "do", "in", "on", "at",
    "to", "for", "of", "and", "or", "say", "said", "sent", "check", "get", "give",
    "please", "thanks", "there", "someone", "anyone", "can", "could", "would",
    "which", "my", "our", "their", "his", "her", "dr", "prof", "mr", "mrs", "ms",
    "who", "whom", "whose", "message", "messages", "inbox", "mail",
})

OVERVIEW_PATTERNS = re.compile(
    r"\b("
    r"what(?:'s|s|\s+is|\s+are)?(?:\s+the)?(?:\s+contents\s+of)?(?:\s+new|\s+recent|\s+latest)?\s+(?:in\s+)?(?:my\s+|the\s+)?(?:recent\s+|latest\s+|newest\s+)?(?:inbox|emails?|messages?|mail)"
    r"|tell\s+me\s+about\s+(?:my\s+|the\s+)?(?:recent\s+|latest\s+|newest\s+)?(?:inbox|emails?|messages?|mail)"
    r"|summariz(?:e|ing)\s+(?:my\s+|the\s+)?(?:recent\s+|latest\s+|newest\s+)?(?:inbox|emails?|messages?|mail)"
    r"|give\s+me\s+(?:an?\s+)?(?:overview|summary|rundown)\s+(?:of\s+)?(?:my\s+|the\s+)?(?:recent\s+|latest\s+|newest\s+)?(?:inbox|emails?|messages?|mail)"
    r"|(?:show|list|check)\s+(?:my\s+|the\s+)?(?:recent\s+|latest\s+|newest\s+)?(?:inbox|emails?|messages?|mail)"
    r"|what\s+emails?\s+(?:do\s+i\s+have|have\s+i\s+received|did\s+i\s+get)"
    r"|what\s+has\s+arrived"
    r"|inbox\s+(?:overview|summary|status)"
    r"|(?:recent|latest|newest)\s+(?:emails?|messages?|mail)"
    r"|any\s+(?:new|recent)\s+(?:emails?|messages?|mail)"
    r")\b",
    re.IGNORECASE,
)

POLICY_PATTERNS = re.compile(
    r"\b("
    r"company\s+policy"
    r"|handbook"
    r"|hr\s+policy"
    r"|code\s+of\s+conduct"
    r"|leave\s+policy"
    r"|remote\s+work\s+policy"
    r"|expense\s+(?:policy|claim|reimbursement)"
    r"|travel\s+(?:policy|reimbursement)"
    r"|guidelines?"
    r"|standard\s+operating\s+procedure"
    r"|sop"
    r")\b",
    re.IGNORECASE,
)


class QueryIntent(StrEnum):
    INBOX_OVERVIEW = "inbox_overview"
    EMAIL_SEARCH = "email_search"
    POLICY_QA = "policy_qa"
    HYBRID = "hybrid"


def classify_intent_deterministic(query: str) -> QueryIntent | None:
    """Tier 1: Fast-path rule floor (<0.1ms) for high-frequency user query intents."""
    cleaned = query.strip()
    if OVERVIEW_PATTERNS.search(cleaned):
        return QueryIntent.INBOX_OVERVIEW
    if POLICY_PATTERNS.search(cleaned):
        return QueryIntent.POLICY_QA
    return None


async def classify_intent_llm(query: str, provider: Provider) -> QueryIntent:
    """Tier 2: Lightweight Gemini 3.5 Flash-Lite intent classifier (~200ms)."""
    prompt = f"""You are a query intent classifier for an enterprise mailbox assistant.
Classify the user query into exactly one category:
- INBOX_OVERVIEW: Broad inquiries asking about recent mailbox activity, mailbox inventory, overview of received messages, or what is currently in the inbox (e.g. "what came in today?", "give me a rundown of recent messages", "status of my inbox").
- EMAIL_SEARCH: Specific queries looking for emails from a particular person, regarding a specific transaction, topic, project, or event (e.g. "did Dr. Asad email me?", "find the Grab receipt", "emails about budgeting").
- POLICY_QA: Inquiries about company policies, compliance, guidelines, employee handbook, or organizational knowledge documents (e.g. "what is the remote work policy?", "how do I expense meals?").
- HYBRID: Complex questions that clearly require correlating personal emails with official company policies.

Query: {query}
Respond with ONLY the category name: INBOX_OVERVIEW, EMAIL_SEARCH, POLICY_QA, or HYBRID."""

    try:
        response = await model_gateway.generate(
            prompt,
            provider=provider,
            purpose=PURPOSE_ROUTE,
            max_output_tokens=16,
        )
        if isinstance(response, str):
            norm = response.strip().upper()
            if "INBOX_OVERVIEW" in norm:
                return QueryIntent.INBOX_OVERVIEW
            if "POLICY_QA" in norm:
                return QueryIntent.POLICY_QA
            if "HYBRID" in norm:
                return QueryIntent.HYBRID
            if "EMAIL_SEARCH" in norm:
                return QueryIntent.EMAIL_SEARCH
    except ModelError as exc:
        logger.warning("LLM intent routing failed, defaulting to HYBRID: %s", exc)

    return QueryIntent.HYBRID


async def route_query_intent(query: str, provider: Provider) -> QueryIntent:
    """Two-tier hybrid query routing: rule floor first, Gemini Flash-Lite fallback."""
    fast_intent = classify_intent_deterministic(query)
    if fast_intent is not None:
        return fast_intent
    return await classify_intent_llm(query, provider)


def extract_sender_candidates(query: str) -> list[str]:
    """Extract potential sender names from user query, stripping honorifics and stop words."""
    cleaned = re.sub(r"\b(?:dr|prof|mr|mrs|ms)\.?\s*", "", query, flags=re.IGNORECASE)
    words = re.findall(r"\b[A-Za-z]{3,}\b", cleaned)
    return [w.lower() for w in words if w.lower() not in QUESTION_STOP_WORDS]


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


HISTORY_QUESTIONS = 3
MAX_HISTORY_TURNS = 20


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class InboxSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=MAX_HISTORY_TURNS)
    k_emails: int = Field(default=5, ge=1, le=20)
    k_docs: int = Field(default=3, ge=1, le=10)
    # False while the reader hides details (say, sharing their screen): placeholders stay in the answer.
    restore: bool = True


class InboxSearchResponse(BaseModel):
    answer: str
    sources: list[SearchSource]
    sender_vault: dict[str, str] = Field(default_factory=dict)
    has_restored_pii: bool = False
    intent: str | None = None


def _shown(text: str, thread_map: ThreadMap, restore: bool) -> str:
    """Text for the reader: details filled in, unless they asked to keep them hidden."""
    return thread_map.restore(text)[0] if restore else text


def _questions(history: list[ChatMessage]) -> list[str]:
    """The user's recent questions only. The assistant's answers carry real names filled back in
    after the model answered, so sending them back would hand those names to the model."""
    asked = [turn.content for turn in history if turn.role == "user"]
    return [mask_typed_text(question) for question in asked[-HISTORY_QUESTIONS:]]


async def contextualize_query(query: str, history: list[ChatMessage], provider: Provider) -> str:
    """Resolve pronouns and conversational context into a self-contained search query."""
    if not history:
        return query

    formatted_turns = "\n".join(f"User: {content}" for content in _questions(history))

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


def _visible(scope: Scope, provider: Provider) -> ColumnElement[bool]:
    """The rows this search may read. A search across users on Gemini leaves out Private mode users,
    whose emails never go to Gemini (a script with the backend token gets every user's scope)."""
    if scope.is_everything and provider == Provider.GEMINI:
        return and_(scope.where(Message.user_id), not_private(Message.user_id))
    return scope.where(Message.user_id)


async def search_messages_hybrid(
    search_query: str,
    k: int,
    *,
    scope: Scope,
    provider: Provider,
) -> tuple[list[Message], list[str]]:
    """Retrieve candidate messages using sender matching and vector similarity.

    Returns a tuple of (matched_messages, sender_candidate_words).
    """
    # Email vectors are Gemini's (migration 0035): Private mode has none, so it matches on words only.
    query_vector = (
        await model_gateway.embed_query(search_query, provider=Provider.GEMINI, purpose=PURPOSE_SEARCH)
        if provider == Provider.GEMINI
        else None
    )

    cleaned_words = extract_sender_candidates(search_query)

    async with get_sessionmaker()() as session:
        # 1. Full-Text Search (Keyword Rank)
        fts_rows: list[Message] = []
        try:
            fts_stmt = (
                select(Message)
                .where(
                    Message.search_vector.op("@@")(func.websearch_to_tsquery("english", search_query)),
                    _visible(scope, provider),
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
                        _visible(scope, provider),
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

        # Check if query matches a sender name locally in PostgreSQL (e.g. "Asad", "Bryan")
        sender_rows: list[Message] = []
        if cleaned_words:
            try:
                conditions = [Message.from_addr.ilike(f"%{w}%") for w in cleaned_words]
                sender_stmt = (
                    select(Message)
                    .where(
                        or_(*conditions),
                        _visible(scope, provider),
                    )
                    .order_by(Message.received_at.desc())
                    .limit(10)
                )
                sender_rows = (await session.scalars(sender_stmt)).all()
            except SQLAlchemyError as exc:
                logger.debug("Sender search query failed: %s", exc)

        # 2. Vector Search with strict relevance threshold (distance <= 0.35 / similarity >= 65%)
        vec_rows: list[Message] = []
        if query_vector:
            try:
                distance = Message.embedding.cosine_distance(query_vector)
                vec_stmt = (
                    select(Message)
                    .where(
                        Message.embedding.is_not(None),
                        _visible(scope, provider),
                        distance <= 0.35,  # Stricter similarity floor (>= 65% similarity)
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
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (3.0 / (RRF_K + rank + 1))

        for rank, msg in enumerate(fts_rows):
            # If a specific sender was targeted, do not include unrelated FTS rows
            if sender_rows and not any(w in (msg.from_addr or "").lower() for w in cleaned_words):
                continue
            message_map[msg.id] = msg
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (1.0 / (RRF_K + rank + 1))

        for rank, msg in enumerate(vec_rows):
            # If a specific sender was targeted, do not include unrelated vector rows
            if sender_rows and not any(w in (msg.from_addr or "").lower() for w in cleaned_words):
                continue
            message_map[msg.id] = msg
            rrf_scores[msg.id] = rrf_scores.get(msg.id, 0.0) + (1.0 / (RRF_K + rank + 1))

        if not rrf_scores:
            return [], cleaned_words

        sorted_ids = sorted(rrf_scores.keys(), key=lambda mid: rrf_scores[mid], reverse=True)[:k]
        return [message_map[mid] for mid in sorted_ids], cleaned_words


def strip_emojis(text: str) -> str:
    """Strip 4-byte astral characters / emojis to ensure clean terminal and enterprise display."""
    return re.sub(r"[\U00010000-\U0010ffff]", "", text)


def format_email_snippet(msg: Message) -> str:
    """Produce a concise excerpt of an email for context and citation display."""
    body = (msg.body_masked or msg.snippet_masked or "").strip()
    clean = strip_emojis(" ".join(body.split()))
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
    """Execute hybrid retrieval across emails and policy docs, synthesizing a grounded answer.

    Enforces local AES-GCM PII vault restoration, sender query grounding, and universal source pruning.
    """
    sanitized_query = mask_typed_text(request.query)

    # Contextualize query with conversational history
    effective_query = await contextualize_query(sanitized_query, request.history, provider)

    # 0. Route query intent via two-tier hybrid router
    intent = await route_query_intent(effective_query, provider)
    logger.info("Resolved query intent: %s", intent)

    matched_emails: list[Message] = []
    sender_candidates: list[str] = []
    matched_docs: list[ContextChunk] = []

    if intent == QueryIntent.INBOX_OVERVIEW:
        # Direct recency retrieval: fetch latest incoming messages without topical distance threshold
        try:
            async with get_sessionmaker()() as session:
                stmt = (
                    select(Message)
                    .where(_visible(scope, provider))
                    .order_by(Message.received_at.desc())
                    .limit(request.k_emails)
                )
                matched_emails = (await session.scalars(stmt)).all()
        except SQLAlchemyError as exc:
            logger.error("Failed to fetch recent messages for inbox overview: %s", exc)
        matched_docs = []

    elif intent == QueryIntent.EMAIL_SEARCH:
        matched_emails, sender_candidates = await search_messages_hybrid(
            effective_query,
            request.k_emails,
            scope=scope,
            provider=provider,
        )
        # Safe fallback: if no emails match targeted search, inspect knowledge base before negative short-circuit
        if not matched_emails:
            try:
                raw_docs = await search_policy_documents(
                    effective_query,
                    request.k_docs,
                    scope=scope,
                    provider=provider,
                )
                matched_docs = [d for d in raw_docs if d.get("similarity_score", 0.0) >= 0.65]
            except (SQLAlchemyError, ModelError) as exc:
                logger.warning("Knowledge base fallback retrieval failed: %s", exc)

    elif intent == QueryIntent.POLICY_QA:
        try:
            raw_docs = await search_policy_documents(
                effective_query,
                request.k_docs,
                scope=scope,
                provider=provider,
            )
            matched_docs = [d for d in raw_docs if d.get("similarity_score", 0.0) >= 0.65]
        except (SQLAlchemyError, ModelError) as exc:
            logger.warning("Knowledge base retrieval failed: %s", exc)
        # Safe fallback: if no docs match, inspect inbox emails before negative short-circuit
        if not matched_docs:
            matched_emails, sender_candidates = await search_messages_hybrid(
                effective_query,
                request.k_emails,
                scope=scope,
                provider=provider,
            )

    else:  # HYBRID
        matched_emails, sender_candidates = await search_messages_hybrid(
            effective_query,
            request.k_emails,
            scope=scope,
            provider=provider,
        )
        try:
            raw_docs = await search_policy_documents(
                effective_query,
                request.k_docs,
                scope=scope,
                provider=provider,
            )
            matched_docs = [d for d in raw_docs if d.get("similarity_score", 0.0) >= 0.65]
        except (SQLAlchemyError, ModelError) as exc:
            logger.warning("Knowledge base retrieval failed during hybrid search: %s", exc)

    # If no candidates found anywhere upfront
    if not matched_emails and not matched_docs:
        negative_msg = (
            "I checked your inbox but found no recent messages."
            if intent == QueryIntent.INBOX_OVERVIEW
            else "I searched your inbox and knowledge base but could not find any relevant emails or documents regarding your query."
        )
        return InboxSearchResponse(
            answer=negative_msg,
            sources=[],
            sender_vault={},
            has_restored_pii=False,
            intent=intent.value,
        )

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

    # 3. Build unified ThreadMap to open all retrieved email vaults securely
    thread_map = ThreadMap()
    for msg in matched_emails:
        details = None
        if msg.pii_vault and msg.gmail_message_id:
            try:
                details = open_vault(msg.pii_vault, msg.user_id, msg.gmail_message_id)
            except VaultUnavailableError as exc:
                logger.warning("Vault for message %s did not open: %s", msg.id, exc)
        thread_map.add_message(str(msg.id), details, f"{msg.subject or ''}\n{msg.body_masked or ''}")

    # 4. Construct grounded synthesis prompt with Strict Zero-Knowledge Sender Anonymization
    candidate_sources_map: dict[str, SearchSource] = {}
    email_blocks: list[str] = []
    sender_vault: dict[str, str] = {}

    # Each email's own placeholder numbers, moved into the one numbering the answer is restored with.
    shared_subjects = {msg.id: thread_map.renumber(str(msg.id), strip_emojis(msg.subject or "").strip() or "(No subject)")
                       for msg in matched_emails}
    shared_snippets = {msg.id: thread_map.renumber(str(msg.id), format_email_snippet(msg)) for msg in matched_emails}
    for idx, msg in enumerate(matched_emails, 1):
        tag = f"[Email {idx}]"
        sender_placeholder = f"[SENDER_{idx}]"
        if msg.from_addr:
            sender_vault[sender_placeholder] = msg.from_addr

        # Check if this sender matches any queried sender term (e.g. Asad, Bryan)
        sender_match_note = ""
        matched_target = next(
            (w for w in sender_candidates if w in (msg.from_addr or "").lower()),
            None,
        )
        if matched_target:
            sender_match_note = f" (Matches queried sender: '{matched_target.capitalize()}')"

        body_text = thread_map.renumber(
            str(msg.id),
            (msg.body_masked or msg.snippet_masked or "").strip()[:1500],
        )

        clean_subject = shared_subjects[msg.id]

        email_blocks.append(
            f"{tag}\n"
            f"Subject: {clean_subject}\n"
            f"From: {sender_placeholder}{sender_match_note}\n"
            f"Date: {format_received_date(msg.received_at)}\n"
            f"Content: {body_text}"
        )

        candidate_sources_map[tag] = SearchSource(
            source_type=SourceType.EMAIL,
            id=str(msg.id),
            title=_shown(clean_subject, thread_map, request.restore),
            subtitle=f"{(msg.from_addr if request.restore else sender_placeholder) or 'Unknown sender'} · "
                     f"{format_received_date(msg.received_at)}",
            snippet=_shown(shared_snippets[msg.id], thread_map, request.restore),
            received_at=msg.received_at.isoformat() if msg.received_at else None,
        )

    doc_blocks: list[str] = []
    for idx, doc in enumerate(matched_docs, 1):
        tag = f"[Document {idx}]"
        info = chunk_docs_map.get(doc["chunk_id"])
        doc_id = info[0] if info else doc["chunk_id"]
        doc_title = info[1] if info else doc["source_title"].split(" · ")[0]
        top_score = int(doc["similarity_score"] * 100)

        doc_blocks.append(
            f"{tag} - {doc_title}\n"
            f"{doc['content'][:1500]}"
        )

        candidate_sources_map[tag] = SearchSource(
            source_type=SourceType.DOCUMENT,
            id=str(doc_id),
            title=doc_title,
            subtitle=f"Knowledge Base · {top_score}% match",
            snippet=doc["content"][:280] + ("..." if len(doc["content"]) > 280 else ""),
            received_at=None,
        )

    emails_section = "\n\n".join(email_blocks) if email_blocks else "None found."
    docs_section = "\n\n".join(doc_blocks) if doc_blocks else "None found."

    questions = _questions(request.history)
    history_text = ("Earlier questions:\n" + "\n".join(f"User: {q}" for q in questions) + "\n\n") if questions else ""

    if intent == QueryIntent.INBOX_OVERVIEW:
        task_instruction = (
            "The user is asking for an overview or summary of their inbox/recent emails.\n"
            "Synthesize a clear, executive overview of their recent incoming correspondence based on the retrieved emails.\n"
            "Format each email as a single clean bullet item:\n"
            "- **[Subject]** — *[Sender]* ([Date])\n"
            "  [One concise sentence summarizing the core takeaway and any required action]. [Email X]\n"
            "CRITICAL FORMAT RULE: Do NOT create separate bullet points for Sender, Date, Subject, or Takeaway. Consolidate each email into one entry.\n"
            "Insert a blank line between each email entry for readability.\n"
            "Keep the summary concise and under 350 words."
        )
    else:
        task_instruction = (
            "Answer the user's question clearly, professionally, and concisely based strictly on the provided retrieved emails and documents.\n"
            "If summarizing multiple emails or documents, consolidate each item into a single entry with Subject, Sender, and Date on the title line, and the takeaway indented underneath.\n"
            "Keep the answer concise and direct (under 400 words)."
        )

    synthesis_prompt = f"""You are AImail's intelligent inbox and knowledge assistant.
{task_instruction}

Rules:
1. Ground your answer completely in the retrieved sources. Do not hallucinate or speculate.
2. Cite the specific sources you use in your answer using their bracketed tags (e.g. [Email 1], [Document 1]). If a sender note indicates a match for the user's queried sender, synthesize the answer identifying that correspondence.
3. If no retrieved sources contain relevant information to answer the question, clearly state that you could not find relevant correspondence or documents, and end your answer with:
Citations: None
4. Keep the tone enterprise-ready, polite, and helpful. Strictly do not use emojis.
5. Structure your response cleanly. Use single consolidated bullets or numbered items per email with clear spacing between entries. Bold subjects and key dates/metrics. Never generate repetitive field-by-field bullet lists (e.g. do not output separate bullets for 'Sender:', 'Date:', 'Subject:', or 'Key Takeaway:').
6. At the very end of your response, on a new line, explicitly list all tags of sources that were directly relevant and used to answer the question:
Citations: [Email X], [Document Y] (or Citations: None)

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
            max_output_tokens=2048,
        )
        if isinstance(answer, str) and answer.strip():
            answer_text = answer.strip()
        else:
            answer_text = "I could not synthesize an answer from the retrieved sources.\nCitations: None"
    except ModelError as exc:
        logger.error("Synthesis generation failed: %s", exc)
        if intent == QueryIntent.INBOX_OVERVIEW and matched_emails:
            overview_lines = ["Here is an executive overview of your recent incoming emails:\n"]
            for idx, msg in enumerate(matched_emails[:5], 1):
                sender_val = sender_vault.get(f"[SENDER_{idx}]", msg.from_addr or "Unknown sender")
                date_val = format_received_date(msg.received_at)
                subj_val = shared_subjects[msg.id]
                snip_val = shared_snippets[msg.id]
                overview_lines.append(f"- **{subj_val}** — *{sender_val}* ({date_val})\n  {snip_val} [Email {idx}]\n")
            citations_list = ", ".join(f"[Email {i}]" for i in range(1, len(matched_emails[:5]) + 1))
            answer_text = "\n".join(overview_lines) + f"\nCitations: {citations_list}"
        elif matched_emails:
            fallback_lines = ["Here are the matching emails found in your inbox:\n"]
            for idx, msg in enumerate(matched_emails[:3], 1):
                sender_val = sender_vault.get(f"[SENDER_{idx}]", msg.from_addr or "Unknown sender")
                date_val = format_received_date(msg.received_at)
                subj_val = shared_subjects[msg.id]
                fallback_lines.append(f"- **{subj_val}** — *{sender_val}* ({date_val}) [Email {idx}]")
            citations_list = ", ".join(f"[Email {i}]" for i in range(1, len(matched_emails[:3]) + 1))
            answer_text = "\n".join(fallback_lines) + f"\n\nCitations: {citations_list}"
        else:
            answer_text = "I encountered an error communicating with the AI model while analyzing your retrieved emails.\nCitations: None"

    # 5. Universal Source Pruning: Parse Citations from Gemini output
    clean_answer = answer_text
    cited_tags: list[str] = []

    citations_match = re.search(r"\n\s*Citations:\s*(.+)$", answer_text, flags=re.IGNORECASE)
    if citations_match:
        citations_line = citations_match.group(1).strip()
        clean_answer = answer_text[:citations_match.start()].strip()
        if "none" not in citations_line.lower():
            cited_tags = re.findall(r"\[(?:Email|Document)\s*\d+\]", citations_line, flags=re.IGNORECASE)

    # Inline tag fallback if citations line was omitted
    if not cited_tags:
        inline_tags = re.findall(r"\[(?:Email|Document)\s*\d+\]", clean_answer, flags=re.IGNORECASE)
        negative_signals = [
            "could not find", "couldn't find", "cannot find", "no relevant", "no emails", "no documents"
        ]
        if not any(sig in clean_answer.lower() for sig in negative_signals):
            cited_tags = inline_tags

    # If the answer explicitly states negative or not found, force empty sources
    negative_phrases = [
        "could not find", "couldn't find", "cannot find", "no relevant emails", "no relevant documents",
        "not find any emails", "not find any documents"
    ]
    if any(p in clean_answer.lower() for p in negative_phrases):
        cited_tags = []

    # Filter candidate sources to ONLY cited sources
    seen_ids: set[str] = set()
    final_sources: list[SearchSource] = []
    for raw_tag in cited_tags:
        norm_tag = re.sub(
            r"\[(email|document)\s*(\d+)\]",
            lambda m: f"[{m.group(1).capitalize()} {m.group(2)}]",
            raw_tag,
            flags=re.IGNORECASE,
        )
        source = candidate_sources_map.get(norm_tag)
        if source and source.id not in seen_ids:
            seen_ids.add(source.id)
            final_sources.append(source)

    if not request.restore:
        return InboxSearchResponse(answer=clean_answer, sources=final_sources, sender_vault={},
                                   has_restored_pii=False, intent=intent.value)

    # 6. Local AES-GCM Vault PII Restoration
    restored_text, _ = thread_map.restore(clean_answer)
    for placeholder, sender in sender_vault.items():
        restored_text = restored_text.replace(placeholder, sender)

    has_restored_pii = bool(
        restored_text != clean_answer
        or any(k in clean_answer for k in thread_map.values)
        or any(k in clean_answer for k in sender_vault)
    )

    return InboxSearchResponse(
        answer=restored_text,
        sources=final_sources,
        sender_vault=sender_vault,
        has_restored_pii=has_restored_pii,
        intent=intent.value,
    )
