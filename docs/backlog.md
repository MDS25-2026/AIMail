# Backlog — scoped 2026-09-07

**Sequenced for the final sprint in [`week10-plan.md`](week10-plan.md); every item below now has an issue on the Week 10 milestone.**

Feature work proposed in a working session, scoped and placed. Distinct from
[`audit-remediation-plan.md`](audit-remediation-plan.md) (the nine audit items) and
[`known-issues.md`](known-issues.md) (defects found in testing).

Week 10 is the final submission. Currently scheduled and **not to be displaced**: prompt-injection
fencing (Lane C), Chrome extension backend wiring (Lane D), attachment OCR (Lane A).

| # | Item | Effort | Lane | Column | Blocked by |
|---|------|--------|------|--------|-----------|
| 1 | Priority-labelling user study | S–M | B (team recruits) | **In progress — start now** | nothing |
| 2 | Index sent mail alongside policy | L | B + A | Planned, last | masking the ingest path |
| 3 | Masking transparency panel | S–M | A + D | Planned | migration |
| 4 | Show the real email, fetched live | M | B + D | Planned, after the pitch | nothing |
| 5 | Configurable inbox sort | S | D | Planned | importance backfill |
| 6a | User profile in drafting prompts | S | B + C | Planned | nothing |
| 6b | Sender priority list | M | B + D | Planned, gated | item 1's findings |
| 7 | Signature role as a classifier feature | S to assess, M to build | B | **Assess only** | nothing |
| 8 | Per-user custom priority rules | — | B | **KIV** | deliberately unbuilt schema |

## 1 · Priority-labelling user study — start this week

8–10 real emails, participants sort into high/medium/low, then explain two or three. Capture job
role. Four questions in one instrument:

- **Human-to-human agreement**, which gives 0.69 a ceiling to be compared against. Right now the
  number floats with nothing to anchor it — if people only agree 70% with each other, 0.69 reads
  very differently.
- **Does the rubric match how people actually sort?** Tests the boundary rules, not just accuracy.
- **Did any email not fit three tiers?** Closes the class-count question with evidence.
- **Would a list of important senders have changed your sorting?** Directly gates item 6b.

**Why this is first.** It is the only item with calendar lead time — participants respond on their
schedule, not ours. It also fills end-user engagement, a named marking element with currently zero
evidence. And it de-risks two other items on this list rather than competing with them.

**Do not let this slip.** It is the highest value-per-hour item here and the only one that cannot
be compressed at the end.

## 2 · Index sent mail alongside policy

Retrieval returns both the relevant policy passage and examples of how the user previously replied.
Closes R03.5. Evaluate blind: policy-only versus policy-plus-tone-examples.

**Hard dependency:** sent mail contains other people's PII and `ingest_text` currently performs no
masking at all (see known-issues). That path must route through `maskText` first, which is a
cross-lane change (A owns masking, B owns ingestion).

**Cheaper than it looks in one respect:** `document.doc_type` already exists, so policy and tone
examples can be filtered apart at retrieval without a schema change.

**Blunt:** this is the largest item here and it competes directly with the extension and fencing
for the same weeks. Do not start it until both of those have landed. If it slips past Week 10, the
blind-eval design is still worth writing up as proposed methodology.

## 3 · Masking transparency panel

Show what the model actually received — side by side, or a badge reading "4 items masked before
this reached the AI".

`emails_masked` and `phones_masked` already exist. Presidio's name and location counts do not:
`maskWithPresidio` already receives `entity_type` per detection and currently discards it, so
capturing counts is a small change there plus a migration.

**Good value.** It is cheap, it is visible in a demo, and it puts evidence behind the user-trust
anticipated issue, which currently has a mitigation and nothing supporting it.

## 4 · Show the real email, fetched live from Gmail

Users must be able to read their actual mail; today they see only the masked copy, so they cannot
verify a draft greets the right person.

**Fetch live, never store.** A backend endpoint reads the message from Gmail by ID using the
existing read scope and returns it without persisting. The privacy claim depends on this: no raw
body column, no cache, and it must not be logged.

**Confirmed safe by design** — this is the same conclusion reached when discussing reversible
masking. The mailbox already holds the original, so nothing extra is stored anywhere.

**Timing:** after the pitch. The current demo narrative deliberately shows the masked copy as the
privacy proof; changing that mid-week undercuts a rehearsed story for no marking gain.

## 5 · Configurable inbox sort

Dropdown for date, priority, deadline, confidence. **Default to date**, so the classifier is
offered rather than imposed — good product judgement and worth saying out loud.

Frontend-only: every email is already in the client cache, so this is a sort function and a select.

**Blocked by the importance backfill** — 15 of 32 messages are unscored, so sorting by priority
today would order most of the inbox by a placeholder.

## 6 · Settings — two features, split them

**6a · User profile** (small). A short paragraph on name, role and responsibilities, injected into
drafting prompts to improve voice. Cheap, improves every draft, no evidence needed first.

**6b · Sender priority list** (medium). Exact-match on `from_addr`, overriding predicted priority.
A lookup table, not RAG, and **it must never enter any prompt** — it is an override applied after
prediction.

**Gate 6b on item 1.** The study asks directly whether a sender list would have changed how people
sorted. Building it first and asking afterwards wastes the question.

**Boundary to hold:** the classifier stays text-only; profile context may inform drafting but never
classification. Mixing them would make the classifier's evaluation incomparable with every number
reported so far.

## 7 · Signature role as a classifier feature — assess, do not build

Assess coverage on the actual corpus first: what fraction of emails carry a parseable role in the
signature? That is a couple of hours and produces a finding either way.

**Do not retrain before Week 10.** Retraining is what produces the headline 0.69, and a
feature-engineering experiment weeks from submission risks destabilising the one number that is
currently defensible. Enron signatures are also inconsistent enough that coverage is likely poor.

A coverage figure with a decision not to proceed is a perfectly good report contribution — better
than a half-finished experiment.

## 8 · Per-user custom priority rules — KIV

Correct to defer, but **the stated reason needs correcting**: there is no interaction store, and
its absence is a deliberate accepted decision (`lane-b-ml.md`, 2026-07-07). The research version
introduced an `interactions` table and a weeks-of-behavioural-logs dependency that no requirement
R01–R12 asks for, and it conflated this classifier with Lane C's draft-learning.

So the honest deferral is: per-user rules need per-user correction data, we have one mailbox, and
capturing corrections would mean adding a table we deliberately decided against on requirement
grounds. Deferred on evidence, and the evidence is already written down.

## The scheduling conflict to watch

Items 3, 4, 5 and 6b all need Lane D time, and Lane D owns the Chrome extension — Goal 1 of the
proposal, currently the largest gap between what was promised and what exists.

**Nothing on this list should displace the extension.** If Lane D capacity is the constraint, the
order is: extension wiring, then 3, then 5, then 4, then 6b. Item 1 needs almost no Lane D time at
all, which is another reason it goes first.
