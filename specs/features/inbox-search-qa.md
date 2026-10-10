# Natural language inbox search and thread Q&A assistant

- **Status:** in-progress
- **Owner:** @HanifRafli
- **Related issue:** #144
- **Last updated:** 2026-10-09

## Goal

Empower knowledge workers to query and understand their email correspondence and corporate policies using natural language (e.g., *"What discount did we agree on with Acme?"*, *"When is the scheduled deployment deadline?"*), combining deterministic keyword retrieval, semantic vector similarity, and anti-hallucination grounded LLM synthesis.

This feature fulfills the deliverable for **Issue #144** and represents the core convergence of **Lane B (Hybrid Retrieval Surface)** and **Lane C (Gemini Q&A Grounding Engine)**, surfaced through an interactive, privacy-first chatbot widget in **Lane D (Dashboard)**.

## User story

As a corporate knowledge worker and inbox operator, I want to ask questions in plain natural language about my past email threads and company policies, so that I can instantly recall critical business agreements, deadlines, and context without manual folder searching or opening third-party tools.

## Scope

**In scope**
- **Hybrid Retrieval Architecture (Lane B)**:
  - PostgreSQL full-text search (`tsvector` with GIN indexing) over email `subject` and `body_masked`.
  - Dense semantic vector search (`pgvector` with HNSW indexing, 1536 dimensions) using `gemini-embedding-001`.
  - Reciprocal Rank Fusion (RRF) merging keyword ranks and semantic cosine distance scores:
    $$\text{RRF Score}(d) = \frac{1}{60 + \text{rank}_{\text{fts}}(d)} + \frac{1}{60 + \text{rank}_{\text{vec}}(d)}$$
  - Joint retrieval across both **Inbox Emails** (`messages` table) and **Knowledge Base Documents** (`document` and `chunk` tables via `app/rag/retrieve.py`).
- **Conversational Answering Engine (Lane C)**:
  - Query contextualization and reformulation for multi-turn conversations resolving anaphora and coreference (e.g., *"When does that expire?"* -> *"Acme pricing discount expiration date"*).
  - Grounded answer synthesis via Google Gemini (`gemini-2.5-flash` or configured `GEMINI_CHAT_MODEL`).
  - Anti-hallucination prompt boundaries strictly citing retrieved email identifiers and document headings.
- **Privacy & Multi-Tenant Security Guardrails**:
  - Upfront PII masking of user queries using `mask_typed_text` before embedding or prompt dispatch.
  - Strict tenant isolation: Queries are bounded by `Scope.where(messages.user_id)` so users can never search or cite another user's email or documents.
  - LLM inputs and retrieved payloads operate exclusively on de-identified masked text (`body_masked`).
- **Dashboard Interactive Chat Widget (Lane D)**:
  - Floating action button (FAB) anchored to the **bottom-left** corner over the navigation sidebar.
  - Expandable/collapsible floating chat card (380px wide) with smooth animations and keyboard accessibility.
  - Ephemeral session memory: In-memory React state per browser session with "New conversation" reset button.
  - Multi-source citation chips (e.g., `[3 sources: 2 emails, 1 document]`) expanding into structured citation cards.
  - Deep linking: Clicking an email source card navigates directly to `/?email=<message_id>`, rendering the thread in the right detail panel without page reload.
  - Mobile-responsive adaptation (<768px): Adapts cleanly to a full-screen or bottom-sheet drawer.

**Out of scope**
- Automated draft dispatch or email generation directly from the search widget (the widget is read-only Q&A).
- Persistent storage of chat logs on the server (chat sessions are strictly ephemeral on the client to protect PDPA compliance and reduce database footprint).
- Searching raw unmasked PII (the search index indexes exclusively masked email bodies).

## Acceptance criteria

- [ ] Given database migration `0035_inbox_search_hybrid.sql`, the `messages` table features a `tsvector` generated column with a GIN index and an `embedding vector(1536)` column with an HNSW cosine index.
- [ ] Given an authenticated user, calling `POST /api/search/inbox` executes dual retrieval across their own masked messages and knowledge base documents, returning a grounded answer and structured sources list.
- [ ] Given an unauthenticated or invalid session, `POST /api/search/inbox` returns `401 signed_out` / `401 session_invalid`.
- [ ] Given a query containing personal data (e.g. phone numbers or IC numbers), `mask_typed_text` replaces them before embedding generation or model egress.
- [ ] Given multi-turn history with pronouns (e.g. "What did they reply?"), the reformulation layer synthesizes a self-contained retrieval query.
- [ ] Given a grounded response citing sources, each email source includes `id`, `title`, `subtitle`, and `snippet`.
- [ ] Given the dashboard UI, a floating chat button is visible in the bottom-left corner and toggles the chat panel.
- [ ] Given a chat response with a sources chip, clicking the chip expands the list of sources, and clicking an email source updates the router URL to `/?email=<id>` and displays that email in the detail view.
- [ ] Given a viewport width <768px (mobile), the chat widget renders as a responsive full-screen sheet or drawer without horizontal overflow.

## REST API Contract

### `POST /api/search/inbox`
- **Auth**: Required (`aimail_session` cookie or `Authorization: Bearer <token>`).
- **Request Body**:
  ```json
  {
    "query": "string (min 1 char)",
    "history": [
      { "role": "user", "content": "string" },
      { "role": "assistant", "content": "string" }
    ],
    "k_emails": 5,
    "k_docs": 3
  }
  ```
- **Response 200**:
  ```json
  {
    "answer": "string",
    "sources": [
      {
        "source_type": "email",
        "id": "uuid",
        "title": "string",
        "subtitle": "string",
        "snippet": "string",
        "received_at": "ISO timestamp | null"
      },
      {
        "source_type": "document",
        "id": "uuid",
        "title": "string",
        "subtitle": "string",
        "snippet": "string",
        "received_at": null
      }
    ]
  }
  ```
- **Error Codes**:
  - `401 signed_out` / `session_invalid`
  - `404 mailbox_not_connected`
  - `422 invalid_request` / `too_large`
  - `503 ai_service_unreachable`
