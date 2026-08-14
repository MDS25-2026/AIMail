# Lane C — Generation

- Owner: Muhammad Hanif Rafli (Hanif)
- Floor: 80% Critic confidence (R03.7 Rubik Pass)
- Covers: Router Agent, reply drafting + tone, Critic Agent, live draft/edit logging
- Seams owned:
  - **Seam 2 (in):** consumes Lane B's top-k context
    `[{chunk_id, content, similarity_score, source_title}]` for prompt construction.
  - **Seam 3 (out):** writes drafts + user edits to `draft` (R08). This is the real
    learn-over-time surface (R08 + R03.5 tone personalization), not Lane B's classifier.

## Log

_No entries yet. Add newest-first using the template in [`README.md`](README.md)._
