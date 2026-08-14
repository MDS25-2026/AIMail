# Lane B — ML + retrieval

- Owner: Elyesa
- Floor: beat the baseline (retrieval metrics + priority classifier)
- Covers: RAG pipeline (embed / store / retrieve), priority classifier, retrieval eval
- Seams owned:
  - **Seam 1 (in):** reads `email.body_masked` from Lane A (JiaJun's actual column name) — PII-free, populated pre-LLM.
  - **Seam 2 (out):** Context Agent returns top-k as
    `[{chunk_id, content, similarity_score, source_title}]` to Lane C. Matches the
    proposal p.15 pseudocode `P = [Q + C + H + thread context]`.

## Log

### 2026-07-07 — Embedding model = gemini-embedding-001 @ 1536 dims
- Decision: embed with `gemini-embedding-001`, `output_dimensionality=1536`, L2-normalized.
  Column pins to `embedding vector(1536)`.
- Why: already in the stack (no new provider/secret), GA and top of MTEB. 1536 fits
  pgvector's **2000-dim HNSW index cap**; the model's native 3072 does not.
- Why not 3072: needs a `halfvec` column to index. Why not 768: less precision headroom
  for R03.2. Why not Voyage/OpenAI: a second provider for no quality we need here.
- Affects: `embedding` table, first migration, `specs/features/rag-retrieval.md`.
- Status: accepted — resolves the unpinned entry below.
- Verified: gemini dims + pgvector HNSW 2000-cap confirmed from current docs (2026-07-07).

### 2026-07-07 — No `interactions` / behavioural-logging table
- Decision: priority classifier trains and evaluates on a **labelled email dataset**, not
  on live opened/replied/archived events. No `interactions` table in the schema.
- Why: R05.1 accepts "priority matches human-labelled ground truth in >=80% of test cases".
  That is a supervised classifier over a labelled set — buildable now, not data-gated.
- Why not the pasted research's version: it introduced an `interactions` table and a
  "wait weeks for behavioural logs" dependency that no requirement (R01-R12) asks for. It
  conflated our priority classifier with Lane C's draft/edit learning (R08 + R03.5).
- Affects: db-schema (priority lives on `email`), Lane B build order (nothing is idle-waiting).
- Status: accepted (2026-07-30) — no `interactions` table in the shipped schema.

### 2026-07-07 — Three-table RAG split (document / chunk / embedding)
- Decision: separate `document` (source), `chunk` (retrieval unit), `embedding`
  (per-model vector). HNSW index on `embedding` with `vector_cosine_ops`.
- Why: lets us re-embed with a new model without touching chunks, and audit which chunks
  came from a replaced/deleted upload. Matches proposal p.15 (chunk PDFs + past sent emails).
- Why not one wide table: collapsing them forces a full re-chunk on any model swap and
  couples source lifecycle to vector lifecycle.
- Affects: db-schema, ingestion + embedding scripts.
- Status: accepted (2026-07-30) — shipped as document/chunk/embedding + 0001_rag_tables.sql.

### 2026-07-07 — Embedding model + dimension UNPINNED (blocking own work)
- Decision: do not create the `embedding vector(N)` column until the model is chosen and
  its dimension confirmed from that model's own docs.
- Why: a wrong `N` fails inserts loudly, but only if pinned to the *real* dim. The research
  guessed 768 (Gemini text-embedding-004); newer Gemini `gemini-embedding-001` defaults
  higher and is configurable. Anthropic has no embeddings API, so Gemini or Voyage are the
  natural picks given the stack already uses Gemini.
- Why not just use 768 now: guessing the dim risks a silent mismatch on the first real insert.
- Affects: `embedding` table, first migration.
- Status: superseded by 2026-07-07 "Embedding model = gemini-embedding-001 @ 1536 dims".

### 2026-07-29 — Lane B build order (slice sequence + AC-forced constraints)
- Decision: build Lane B in seven slices, one branch + one verifiable step each, in this order:
  - **S0 Environment + primitive.** Stand up `backend/app/` (Python package, `pyproject.toml`,
    `db/migrations/` dir) alongside `main.go` — do not touch the Go file (Lane A). Prove the
    primitive: embed one string -> insert -> cosine-query it back. Assert `‖v‖ ≈ 1` as a *test*,
    not a comment (L2-normalize fails silently; scores just degrade — `rag-retrieval.md:103`).
  - **S1 Schema then migration.** Add `document` / `chunk` / `embedding` to
    `specs/context/db-schema.md` first (its own rule: table before migration), then the migration.
    HNSW `vector_cosine_ops` on `embedding vector(1536)`.
  - **S2 Ingest + embed.** PDF -> chunk (512/128 start) -> batch-embed, `model_name` on every row.
    Two easy-to-miss ACs get explicit tests: re-upload *replaces* not duplicates
    (`rag-retrieval.md:79`); partial run *resumes* (`:77`).
  - **S3 `retrieve()` — raw masked email as query.** Exact `ContextChunk` TypedDict
    (`rag-retrieval.md:44-51`). Empty KB returns `[]`, no raise. **This number is the baseline.**
  - **S4 Eval harness.** precision@k / recall@k, R03.2 >=90% bar. Must exist *before* S5.
  - **S5 Query reformulation (R03.1).** Validated by S4 against the S3 baseline. Query-construction
    must be a swappable function so baseline vs reformulated is one flag.
  - **S6 Priority classifier.** Starts with a spec that does not exist yet (scoped out at
    `rag-retrieval.md:28`); CLAUDE.md forbids feature code without one. Spec must satisfy *both*
    R05.1 (>=80% vs human-labelled ground truth) *and* the build-split floor (beat TF-IDF+LR
    baseline) — metric table reports accuracy AND the delta. Promote "No `interactions` table"
    (below) to accepted here, or reopen it.
- Why this order, not the pasted research's: R03.1's AC (`rag-retrieval.md:34`) defines
  reformulation success as beating the raw-query precision@k on the eval set. The harness (S4)
  and a baseline (S3) must therefore precede reformulation (S5). The research put eval last.
- Cross-file gates that land in S0 (CLAUDE.md mandates them): add a Gemini row to
  `specs/context/tech-stack.md` (AI table lists only `claude-opus-4-7`); embedding key name to
  `.env.example` with a comment, never the value; confirm the chunk-sizing tokenizer is in the
  dependency file before importing (`rag-retrieval.md:71`); the Gemini SDK add is "ask first" —
  batch all dependency adds into one ask.
- Deferred, non-blocking (S0-S5 are policy-docs-only): `db-schema.md:32` `email_embedding`
  overlaps `embedding`, and past-sent-email retrieval as `doc_type` vs a Lane C tone path
  (`rag-retrieval.md:93`) is open. Mark before it gets built twice; cross-lane -> log in `shared.md`.
- Seam 2: send Hanif the `ContextChunk` TypedDict now, parallel to S0 — locks the contract
  before either side builds (`rag-retrieval.md:53`). Seam 1 stays a fixture string until Lane A
  ships `email.masked_body`; the n8n-vs-Go-webhook drift does not touch Lane B (we read a column).
- Status: accepted — sprint work may proceed slice by slice.

### 2026-07-30 — S0-S3 verified end-to-end on live infra; S4 harness landed
- embed -> store -> cosine-retrieve proven on Supabase + Gemini (smoke score 0.82 on a
  paraphrase query). S0-S3 done.
- S4 eval harness (precision@k / hit-rate / MRR, marker-based relevance) built + offline-tested;
  runs once a real corpus is ingested. Error-wrap added to embed_texts.
- Setup hurdles resolved: Supabase free tier needs the IPv4 **session pooler** (not direct 5432);
  a Windows-hosts sinkhole had pointed `generativelanguage.googleapis.com` at 127.0.0.1.
- Next: ingest real policy PDFs (exercises ingest/embed_pending), populate the eval set, then S5
  reformulation measured against the S4 baseline.

### 2026-07-30 — Sentence-aware chunking (replaces fixed word-window)
- Change: `chunk_text` now packs whole sentences up to ~380 words (96 overlap) so a chunk never
  cuts mid-sentence. Sentence boundary = `.!?` followed by a capital, so periods inside numbers
  ("1.75", "30 days.") do not split wrongly.
- Why: fixed word-windows cut mid-sentence, degrading embedding/retrieval quality at chunk
  boundaries. Whole sentences keep each chunk semantically intact.
- Verified: 19 tests pass; Code of Conduct PDF -> 10 chunks, all ending on sentence punctuation.
- Apply: re-ingest existing documents (stored chunks are immutable) for the change to take effect.

### 2026-07-30 — S3 retrieval baseline measured (Code of Conduct, 8-query eval)
- Baseline (raw query, k=5): **hit_rate 1.000, precision@5 0.400, MRR 0.817**.
- Headroom: "benefit my relatives" hits at rank 5, "personal situation clashes" at rank 3 —
  low-ranked relevant chunks are what S5 (query reformulation) targets.
- Eval-method note: keyword markers under-count semantically-correct retrievals (the relatives
  query needed "related persons"/"spouses" synonyms added to be credited). LLM-as-judge is the
  rigorous upgrade if we want defensible relevance labels.
- This is the number S5 must beat on the same eval set.

### 2026-07-30 — Priority classifier design settled (see priority-classifier.md)
- Taxonomy = 3-level **importance** (LOW / MEDIUM / HIGH), trained from text only.
- Priority is **composite**: learned importance + a deterministic time-to-deadline layer; calendar
  conflicts deferred (needs Calendar API). Live urgency is computed at display, never stored (a
  date's urgency changes with when it is read). Raised by the technical advisor.
- Label the email's importance, not the date's urgency, so labels stay stable.
- Dataset: hand-label ~300-500 Enron emails against the rubric; pre-labelled spam set as a pipeline
  rehearsal. Full rubric + format in `specs/features/priority-classifier.md`.
