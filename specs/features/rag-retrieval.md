# RAG retrieval (policy grounding)

- **Status:** draft
- **Owner:** @veyroxie
- **Related issue:** #
- **Last updated:** 2026-07-07

## Goal

Ground reply drafts in company policy by retrieving the most relevant policy-document chunks for an incoming email, and hand them to the generation lane as structured context. This is Lane B's **Seam 2** output.

## User story

As the reply generator (Lane C), I want the most relevant company-policy passages for the email I'm answering, so that drafts cite real policy instead of hallucinating it.

## Scope

**In scope**
- Ingest policy PDFs uploaded by an IT admin: extract text, chunk, store.
- Embed each chunk with `gemini-embedding-001` at 1536 dims and store the vector.
- At draft time: reformulate the masked email into a retrieval query (R03.1), embed it, cosine top-k against the policy chunks, return structured context.
- A lightweight retrieval eval harness (hand-labelled query -> expected-chunk set) to measure precision@k and prove we beat a baseline.

**Out of scope**
- Reply generation and tone/style personalization (Lane C; R03.5, R11).
- User past-sent-email / tone retrieval — related but a separate retrieval mode; see Open questions.
- OCR and PII masking of the email (Lane A; the email arrives already masked).
- The priority classifier (separate Lane B spec).

## Acceptance criteria

- [ ] Given a policy PDF is uploaded, when ingestion runs, then each resulting `chunk` row has non-empty `content`, a `token_count`, a `chunk_idx`, and an FK to its `document`.
- [ ] Given a stored chunk, when embedding runs, then an `embedding` row exists with a 1536-dim L2-normalized vector and the `model_name` recorded.
- [ ] Given an incoming masked email, when retrieval runs, then the email is reformulated into a retrieval query before embedding (R03.1), and the reformulation demonstrably improves precision@k over using the raw email as the query on the eval set.
- [ ] Given a retrieval query, when top-k cosine search runs, then it returns a list of `{chunk_id, content, similarity_score, source_title}` ordered by descending `similarity_score`.
- [ ] Given the hand-labelled eval set, when retrieval runs, then a relevant chunk is returned for >=90% of test queries (R03.2).
- [ ] Given an empty knowledge base, when retrieval runs, then it returns an empty list without error (Lane C degrades to no-policy-grounding, does not crash).

## API surface

Internal to the Python backend (not a public REST endpoint). The contract that crosses a lane boundary is the **return shape** consumed by Lane C:

```python
class ContextChunk(TypedDict):
    chunk_id: UUID
    content: str
    similarity_score: float   # cosine, 0..1
    source_title: str

def retrieve(masked_email: str, k: int) -> list[ContextChunk]: ...
```

This is Seam 2. It matches the proposal's Figure 1 pseudocode `P = [Q + C + H + thread context]`, where this function produces `C`. Lock the shape with Lane C (Hanif) before either side builds against it.

## Data model

Three tables (the canonical RAG split). To be added to [`../context/db-schema.md`](../context/db-schema.md) in the same PR — that file is still a TODO skeleton, so this spec is the first real proposal for it (see `docs/decisions/shared.md` on schema authority).

- `document` — id, source, title, doc_type, uploaded_at, timestamps.
- `chunk` — id, document_id (FK), chunk_idx, content, token_count, metadata (jsonb), timestamps.
- `embedding` — id, chunk_id (FK), `embedding vector(1536)`, model_name, created_at.
  - Index: `CREATE INDEX ON embedding USING hnsw (embedding vector_cosine_ops);`

Separating `embedding` from `chunk` lets us re-embed with a new model without re-chunking.

## Dependencies

- **Seam 1:** `email.body_masked` from Lane A (JJ) — PII-free, populated before any LLM call.
- **Gemini embeddings API** (`gemini-embedding-001`) — same provider/key as the classifier tier.
- **Supabase + pgvector** with the `vector` extension enabled.
- A tokenizer for chunk sizing — verify the exact library before use (do not import on assumption).

## Edge cases & failure modes

- **Query exceeds the model's max input tokens** — truncate or split the reformulated query; log when it happens.
- **PDF with no extractable text** (scanned image) — routes to OCR upstream (Lane A); if still empty, the document produces zero chunks and is flagged, not silently dropped.
- **Embedding API rate limit / failure** — retry with backoff; ingestion is idempotent per chunk so a partial run can resume.
- **No chunk above the similarity threshold** — return empty list (see AC), do not fabricate.
- **Duplicate uploads** — same source re-uploaded should replace, not duplicate, its chunks/embeddings.

## Security & privacy notes

<!-- BEGIN PROTECTED -->
Only masked text is ever sent to the embeddings API. The retrieval query derives from `email.body_masked`; if user past-sent emails are later added as a corpus, they must be PII-masked before embedding. Embedding is an external LLM call and is bound by the same server-side masking boundary as every other external call (R02.1).
DO NOT change this without explicit approval from the Lane A / security owner.
<!-- END PROTECTED -->

## Open questions

- Chunk size and overlap — start at ~512 tokens / ~128 overlap, tune against the eval set.
- Which model reformulates the query (R03.1) — Gemini Flash (already in the stack) is the default candidate.
- `k` and the similarity-score cutoff — pick from eval-set behaviour, not a guess.
- How user past-sent emails enter retrieval (a `doc_type` in `document`, or a separate tone-retrieval path owned by Lane C). Decide with Hanif.

## Out-of-scope future extensions

- Metadata pre-filtering (by `doc_type`, recency) before the vector search.
- Re-ranking the top-k with a cross-encoder.
- Self-RAG-style "should I retrieve at all" gating (the proposal already defers this to the Critic Agent).

## Implementation notes

- Call the embeddings API with `output_dimensionality=1536` and **L2-normalize** the result — MRL sub-vectors are not unit-norm, and cosine assumes normalized vectors.
- Batch embedding calls during ingestion; store `model_name` on every row so a model swap is a clean re-embed.
- `gemini-embedding-001` default is 3072 dims, which **exceeds pgvector's 2000-dim HNSW limit** — 1536 is the deliberate pin (see Decisions). Full rationale in `docs/decisions/lane-b-ml.md`.
- Likely files: `backend/app/rag/{ingest,embed,retrieve}.py` (paths to confirm against the backend layout).

## Decisions

- 2026-07-07: Embedding model = `gemini-embedding-001` at 1536 dims. Rationale: already in the stack (no new provider), GA and top of MTEB, and 1536 fits pgvector's 2000-dim HNSW cap while MRL keeps quality. Alternatives: Voyage/OpenAI (extra provider), 3072 (needs `halfvec`), 768 (less precision headroom).

## Protected decisions

<!-- BEGIN PROTECTED -->
The `embedding` column is `vector(1536)`. This is bounded by pgvector's 2000-dim HNSW index limit; the model's native 3072 cannot be HNSW-indexed on the standard `vector` type.
DO NOT raise the dimension above 2000 on the `vector` type without switching the column to `halfvec` and re-benchmarking the index.
<!-- END PROTECTED -->
