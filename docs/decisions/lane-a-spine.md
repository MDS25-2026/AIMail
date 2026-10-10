# Lane A — Spine + privacy

- Owner: Ho Jia Jun (JJ)
- Floor: 80% masking accuracy
- Covers: OAuth, Gmail ingestion, PII masking (Presidio), storage + audit log
- Seams owned:
  - **Seam 1 (out):** `messages.body_masked` — the PII-free field every downstream lane reads.
    Populated before any external LLM call. Changing its name/shape breaks Lanes B and C.
  - **Seam 4 (token):** OAuth token storage shape, if OAuth lands here (proposal puts
    ingestion/OAuth on the Go webhook).

## Log

### 2026-10-10 — Postcodes, car plates and grouped bank numbers are masked, gated on nearby words
- Decision: three Presidio ad-hoc recognisers in `listener/main.go`. Malaysian postcodes (five digits)
  become `LOCATION` near address words (jalan, taman, poskod, kuala...). Car plates (`WXY 1234`)
  become `ACCOUNT` near vehicle words. Grouped bank numbers (three or more groups, never an ISO date)
  join the account recogniser and its context words.
- Why: each is identifying, and none was masked (epic #138 line 49).
- Why `ACCOUNT` for plates, not a new kind: placeholder kinds are a contract across the listener,
  the backend vault and redaction, and the dashboard. `ACCOUNT` is already the fallback for
  identifiers, so no other service changes.
- For whoever adds the next recogniser: Presidio compiles patterns case-blind (force case with
  `(?-i:...)`) and matches context words as substrings ("car" fires on "card", "acc" on "accept").
  Measure on stored mail before shipping; the first plate pattern hit nine false positives that way.
- Not changed, for review: the older digit-run rule still masks a year after "transfer" or "payroll",
  and any digit run after "accept" (it contains "acc").
- Only email bodies and attachments: uploaded documents (`backend/app/rag/mask.py`) are not covered.
- Affects: Lane A. Status: proposed — JiaJun review pending as lane owner.

### 2026-09-03 — Country and state names are kept; cities and streets stay masked
- Decision: `LOCATION` hits naming a country or a Malaysian state are filtered out of the Presidio
  results before anonymising (`allowedLocations` in `listener/main.go`). Cities, districts and
  street names continue to be masked.
- Why: an adversarial test email produced "The [Redacted] desk" from "The US desk". A country or
  state in business mail is organisational context, not personal data — masking it strips meaning
  from the draft the model then writes, without protecting anyone. Confirmed the same for UK,
  Singapore, Malaysia and Selangor.
- Why not drop LOCATION entirely: that would stop masking cities, and "Kuala Lumpur" beside a
  person's name is identifying in a way "Malaysia" is not.
- Why not extend the list to cities: it would punch a hole in the privacy claim. The boundary errs
  conservative — anything ambiguous stays redacted. Keep the list short.
- Note: one earlier fixture expected `Selangor` to be masked. It contradicted this policy and was
  retired; the recall harness surfaced the conflict rather than silently reporting a miss.
- Affects: Lane A. Two other changes shipped alongside — `CREDIT_CARD` added to the requested
  entities (Luhn-validated, so it cannot fire on invoice numbers), and employee/staff/payroll added
  to the account recogniser's context words.
- Status: accepted — JiaJun review pending as lane owner.


_No entries yet. Add newest-first using the template in [`README.md`](README.md)._
