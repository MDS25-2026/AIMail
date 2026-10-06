# Priority classifier (email triage)

- **Status:** draft
- **Owner:** @veyroxie
- **Related issue:** #
- **Last updated:** 2026-07-30

## Goal

Give every incoming email a priority for the dashboard (R05.1), and give Lane B a defensible
ML deliverable: a **trained importance classifier** evaluated against a named baseline.

Priority is **composite**, split by concern:
- **Importance** — does this email need me to act? Learned from the text by the trained model.
- **Temporal urgency** — how soon is any deadline, relative to now? Computed deterministically,
  not learned (rules beat ML at date math, and a date's urgency changes with when it is read).
- **Calendar conflicts** — out of scope (needs Calendar API; it is scheduling logic, not
  classification). Deferred.

The trained model is the "trained a model, beat a baseline" FYP evidence; the temporal layer is
a thin deterministic add-on.

## User story

As a corporate employee, I want incoming emails ranked by how much they need my attention, so
that the dashboard surfaces what matters first instead of a flat chronological list.

## Scope

**In scope**
- Train a supervised **importance** classifier (3 levels: LOW / MEDIUM / HIGH) on a labelled
  email dataset, from text only.
- A **baseline** (TF-IDF + logistic regression) and a **primary model** (fine-tuned small
  transformer, e.g. DistilBERT). The primary must beat the baseline on macro-F1.
- Evaluation: stratified train/test split, confusion matrix, per-class precision/recall/F1.
- A **deterministic temporal layer**: extract a deadline/meeting date from the email, compute
  days-until, and combine with importance into a live priority score.
- Inference surface: `classify_importance(masked_email)` (the model) + `priority_score(...)`
  (the combiner).

**Out of scope**
- **Calendar-conflict awareness** (is something already booked before the date) — needs the
  Google Calendar API; deferred to future extensions.
- Layer 1 routing classification (the LLM that emits the pipeline routing JSON) — an LLM call
  owned by Lane C in [`../agent-pipeline.md`](../agent-pipeline.md), **not** a trained model.
- Behavioural / `interactions`-style logging (rejected, see `docs/decisions/lane-b-ml.md`).
- Draft/edit learning and model-feedback routing (Lane C; [`./model-feedback-routing.md`](./model-feedback-routing.md)).
- RAG retrieval ([`./rag-retrieval.md`](./rag-retrieval.md)).

## Acceptance criteria

- [ ] Given the labelled dataset, when training runs, then it produces a **stratified** split and
      reports per-class sizes.
- [ ] Given the test split, when the baseline (TF-IDF + logistic regression) is evaluated, then a
      confusion matrix and per-class precision/recall/F1 are reported.
- [ ] Given the test split, when the primary model is evaluated, then it **beats the baseline on
      macro-F1 by the agreed margin** on the same held-out set.
- [ ] Given the held-out test set, importance predictions match human labels in **>=80% of cases**
      (R05.1).
- [ ] Given an incoming email, `classify_importance` operates **only on masked text** and returns an
      `Importance` value plus a confidence in `[0, 1]`.
- [ ] Given an email with an explicit date and a `now`, `priority_score` combines importance with
      days-until-deadline; given no extractable date, it returns importance alone (no crash).
- [ ] Given an empty or whitespace-only body, `classify_importance` returns LOW at low confidence and
      does not raise.

## API surface

Internal to the Python backend (not a public REST endpoint until Lane D consumes it).

```python
class Importance(IntEnum):      # what the TRAINED model predicts, from text only
    LOW = 0
    MEDIUM = 1
    HIGH = 2

class ImportanceResult(TypedDict):
    importance: Importance
    confidence: float           # 0..1
    model_version: str

def classify_importance(masked_email: str) -> ImportanceResult: ...

# Deterministic layer (no training). days_until is None when no date was extracted, in which
# case the score is importance alone. Exact formula is tunable; a near deadline lifts the score.
def priority_score(importance: Importance, days_until: int | None) -> float: ...
```

## Data model

Store only what is **stable**; compute live urgency at display so it is never stale:

- `email.importance` — `SMALLINT` (the `Importance` value; the model's stable output).
- `email.importance_confidence` — `REAL`.
- `email.importance_model_version` — `TEXT` (so a retrain is a clean re-score).
- `email.deadline_at` — `TIMESTAMPTZ NULL` (extracted date, stable).
- **`priority_score` is NOT stored** — the dashboard (Lane D) computes it from `importance` +
  (`deadline_at` - now) at render time, because the same email's urgency changes with when it is read.

The `email` table is owned by Lane A and is a TODO in [`../context/db-schema.md`](../context/db-schema.md).
These columns get added there when Lane A defines `email` — coordinate, do not create `email` from Lane B.

## Labelling rubric (3-level importance)

Label by **what the email asks of the recipient**, NOT by the date it mentions. A meeting request
is HIGH whether the meeting is tomorrow or next month — the date's urgency is handled by the
temporal layer, not the label. This keeps labels stable (the same email always gets the same label).

- **HIGH** — needs the recipient to act or decide: a direct request or instruction, a meeting /
  scheduling request, an approval or deadline, an escalation, a question expecting a reply.
- **MEDIUM** — relevant, may need attention, but no direct action: FYI with implications, CC'd on a
  decision, updates on your work, a non-time-critical reply expected.
- **LOW** — no action needed: newsletters, mass announcements, automated notifications, receipts.

### Dataset

- **Format:** one row per email, `text,label` (CSV or JSONL), `label` in {LOW, MEDIUM, HIGH}. No
  pre-split — the training code does the stratified split.
- **Real deliverable:** hand-label ~300-500 Enron emails against this rubric (Enron is raw / unlabelled).
- **Pipeline rehearsal:** the pre-labelled public spam/ham set validates the whole
  baseline -> transformer -> F1 pipeline before Enron labelling is finished. Off-mission for the
  product, but a free, clean second "trained + evaluated" result.
- Aim for >=50-100 examples of the smallest class (HIGH is naturally rarer) or the model just
  predicts MEDIUM/LOW always.

## Dependencies

- **Labelled dataset** (above) — the critical path; owner is compiling it.
- **Seam 1:** `email.body_masked` from Lane A — fixture string until Lane A lands it.
- `scikit-learn` (baseline) — **dependency add, ask first.**
- `transformers` + `torch` (primary) — **heavy dependency add, ask first;** confirm CPU feasibility.
- A date-extraction library for the temporal layer (e.g. `dateparser`) — **ask first;** used by the
  deterministic layer, not the model.

## Edge cases & failure modes

- **Class imbalance.** HIGH is rarer; a model predicting MEDIUM/LOW always can look accurate. Grade on
  **macro-F1 and per-class recall**, stratified splits.
- **Label noise.** Raters disagree; the rubric above is the ground truth. Record inter-annotator
  agreement on a shared subset if feasible.
- **Ambiguous / no date.** `priority_score` falls back to importance alone.
- **Non-English email.** Out of scope (English-only); flag as unclassified rather than mis-score.
- **Dataset PII.** Enron contains real PII; it passes the masking boundary before training, noted for ethics.

## Security & privacy notes

<!-- BEGIN PROTECTED -->
Inference runs on masked text only (`email.body_masked`). If a real email corpus is used for
training, it is PII-masked before any processing. Priority is a read-only signal for display and
ordering — it MUST NOT trigger any automated action, and in particular never an auto-send (reinforces R04.4).
DO NOT change this without explicit approval from the Lane A / security owner.
<!-- END PROTECTED -->

## Open questions

- **"Beat the baseline by how much"** — proposal: primary beats baseline macro-F1 by **>=5 points**
  AND hits R05.1's >=80%. Needs team sign-off.
- **Temporal formula** — how much a near deadline lifts the score, and the day thresholds. Tune once
  there is labelled data; not load-bearing for the model.

## Out-of-scope future extensions

- **Calendar-conflict awareness** — using the user's calendar to raise priority when something is
  already booked before a requested date. Needs Google Calendar integration.
- Online learning from user re-prioritisation (would reintroduce behavioural logging; deferred).
- Per-user calibration (a VIP for one user is noise for another).

## Implementation notes

- Likely files: `backend/app/ml/{dataset,baseline,train,classify}.py` and a small
  `backend/app/ml/temporal.py` for date extraction + `priority_score` (paths to confirm).
- Build the baseline first and freeze its number — it is the bar the transformer must clear.
- Persist metrics (confusion matrix, per-class F1, baseline delta) to a file the FYP report can cite.
- Keep the temporal layer pure and unit-tested (deterministic date math is easy to test offline).

## Decisions

- 2026-07-29: Trained supervised classifier, baseline = TF-IDF + logistic regression, primary =
  fine-tuned small transformer. Rationale: a named baseline makes "beat X" defensible.
- 2026-07-30: **Composite priority = learned importance (text) + deterministic temporal urgency
  (date vs now); calendar conflicts deferred.** Rationale: a text classifier cannot compute urgency
  that depends on the current date or the calendar, and baking a date's urgency into a training label
  makes the label unstable. Separating concerns keeps the model's job learnable and the date math exact.
  Raised by the technical advisor. Alternatives: single learned priority axis (unstable labels on
  time-sensitive email); classify on the deadline date (ignores that urgency is relative to now).
- 2026-07-30: **Taxonomy = 3 levels (LOW / MEDIUM / HIGH).** Rationale: enough for a triage dashboard,
  few enough to label consistently and keep examples-per-class up. Alternatives: 2 (too coarse), 4
  (HIGH-vs-URGENT fuzzy, worse imbalance).

## Protected decisions

<!-- BEGIN PROTECTED -->
This is a **trained, evaluated** importance classifier with a baseline comparison — not an LLM
zero-shot call. The baseline-vs-primary metric comparison is the load-bearing deliverable and must
be preserved even if the primary model changes.
DO NOT reduce this to a single LLM prompt without reopening the Lane B floor ("beat the baseline") with the team.
<!-- END PROTECTED -->
