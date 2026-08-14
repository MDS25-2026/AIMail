# Lane A — Spine + privacy

- Owner: Ho Jia Jun (JJ)
- Floor: 80% masking accuracy
- Covers: OAuth, Gmail ingestion, PII masking (Presidio), storage + audit log
- Seams owned:
  - **Seam 1 (out):** `email.masked_body` — the PII-free field every downstream lane reads.
    Populated before any external LLM call. Changing its name/shape breaks Lanes B and C.
  - **Seam 4 (token):** OAuth token storage shape, if OAuth lands here (proposal puts
    ingestion/OAuth on the Go webhook).

## Log

_No entries yet. Add newest-first using the template in [`README.md`](README.md)._
