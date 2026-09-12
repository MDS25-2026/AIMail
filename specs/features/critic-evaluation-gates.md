# Critic redesign: four purpose-built evaluation gates

- **Status:** implemented at the Lane B owner's direction — **pending Hanif's review**
- **Owner:** @veyroxie drafted; **Lane C (Hanif) owns the file and the call**
- **Related issue:** #9
- **Last updated:** 2026-09-11

## Goal

Replace one self-graded scalar with four gates that each use a mechanism suited to what they
check, so the human-review flag fires on something measurable instead of on a number the model
invents about its own work.

## Why now — the measured evidence

All figures from `make eval-critic` over the 120-email human-labelled holdout. Raw results are
gitignored (`backend/*.csv`); the harness is `backend/scripts/eval_critic.py`.

**The review gate has never fired.** Across 43 drafts in two conditions, not one final confidence
fell below the 0.8 threshold. Observed values were only 0.8, 0.85, 0.9, 0.95 and 1.0.

**Because the repair runs before the check.** `email_agent.py:260` refines *while* confidence is
under `CONFIDENCE_THRESHOLD`; `:273` then sets `needs_human_review` from the same constant. One
number doing two jobs, with the loop resolving anything that would trip the flag. Two drafts came
back with `attempts=1`, so their initial score *was* below 0.8 — the gate engaged internally and
the result is invisible downstream.

**The four real checks are discarded.** `grounding_ok`, `pii_clean`, `tone_match` and
`completeness` appear in exactly two places repo-wide: the prompt text and the response schema. No
Python reads them. They are computed, returned, and dropped — except into `refine_reply`'s prompt,
which fired on 2 of 35 emails. For the other 33, four safety checks were computed and binned while
the gate ran on the undefined scalar.

**Stored confidence is contaminated.** `dashboard.py:120` does
`float(generated.get("confidence") or 0.0)`. The NA path returns `confidence: None`, so
"no draft was generated" is stored as `0.0` — indistinguishable from "the critic rejected this".
Of 11 zero rows in `messages`, **10 have no draft at all**. Every statistic over
`critic_confidence` is affected.

**It is nondeterministic.** The same email produced different `attempts` counts across two runs. No
temperature is set in `call_gemini`, so it runs on the API default.

### This reproduces documented failure modes

Framing matters for the report: this is a replication, not a defect report.

- **Verbalized-confidence miscalibration.** Xiong et al., ICLR 2024 (arXiv 2306.13063) observed
  confidence "primarily range between 80% and 100%, often in multiples of 5". Our distribution is
  0.85 / 0.9 / 0.95 / 1.0 — multiples of 5 between 80% and 100%.
- **Self-preference bias.** Wataoka, Takahashi and Ri (arXiv 2410.21819, NeurIPS 2024 workshop)
  quantify judges preferring text from their own family. Our drafter and critic are both Gemini.
- **Single-model self-feedback.** Self-Refine (Madaan et al., arXiv 2303.17651) uses "a single LLM
  as the generator, refiner, and feedback provider" — a precise description of this pipeline.

## Scope

**In scope** — four gate mechanisms, the gate composition, and the threshold question.

**Out of scope**
- Prompt-injection fencing. It is the higher priority and must not be displaced by this.
- Any change to the priority classifier or its evaluation.
- The completeness gate's actionability precondition (see Dependencies).

## The four gates

### Gate 1 — `pii_clean`: deterministic, hard gate

Stop asking the model. The draft is generated from masked text, so any real address, phone number
or IC in it was invented or leaked — a containment check, not a judgement.

Run Presidio over the **generated draft**, not only the input. Justified independently of the
containment argument by the training-data-extraction literature (Carlini et al. 2021; Lukas et al.
2023; PII-Scope, arXiv 2410.06704): models emit memorised PII they were never given in context, so
the pre-LLM masking layer does not cover it.

Malaysia has no predefined Presidio recognizer. Add a custom `PatternRecognizer` for NRIC
(`YYMMDD-PB-###G`) with context words "IC", "NRIC", "MyKad". The analyzer's REST API accepts
**ad-hoc recognizers per request**, so this needs no change to the container image.

Measure with span-level precision/recall/F1 on a hand-labelled set, in the i2b2/n2c2 tradition.

### Gate 2 — `grounding_ok`: claim decomposition plus entailment

Replace the holistic yes/no with a RAGAS-style faithfulness fraction: decompose the draft into
claims, check each against the retrieved chunks with a local NLI model (DeBERTa-v3-MNLI) or
SummaC-style aggregation. Related primary work: FActScore (arXiv 2305.14251), SummaC
(arXiv 2111.09525), FactCC (arXiv 1910.12840), QAGS (arXiv 2004.04228).

**Cosine similarity cannot be the verdict.** Embeddings are documented as insensitive to negation
and value substitution, which is exactly the dangerous error class — "RM500" and "RM5,000" are
near-identical vectors. Keep it as a triage step that localises which sentences to verify.

Add a deterministic check on numbers, dates and named entities appearing verbatim in the source.
**Present this as an engineering augmentation, not a published metric** — it is not in the standard
canon and should not be attributed to a paper.

### Gate 3 — `tone_match`: advisory, not a gate

Style-strength metrics are noisy (classifier accuracy around 0.79 in reported setups), the GYAFC
authors themselves flag automatic-metric unreliability, and a human approves every send. Blocking a
factually correct, PII-clean, complete draft on subjective style is the wrong trade.

Surface a formality or politeness score to the reviewer. Do not gate on it.

### Gate 4 — `completeness`: per-item coverage, advisory

`extract_actions()` already produces a list, stored in `messages.action_items`. Check each item
against the draft rather than asking for one holistic verdict, so "incomplete" becomes "did not
address item 2 of 3".

**This gate inherits `extract_actions()` recall**, which we measured — see Dependencies. It should
be advisory, not blocking: 90-96% of clinical decision-support alerts are overridden in published
studies, and a noisy hard gate produces exactly that desensitisation.

## Gate composition

```
hard_fail = (not pii_clean) or specifics_unsupported
soft_fail = incomplete or confidence < REFINE_THRESHOLD

refine while soft_fail (max 3)
needs_human_review = hard_fail or soft_fail or attempts > 0
```

Two changes worth noting. **Separate the refine threshold from the review threshold** — one constant
currently does both jobs, which is why the flag never fires. And **`attempts > 0` is a better review
signal than any score**: "the model could not get this right first time" is observable and
meaningful, where a self-reported 0.95 is not. `critic_attempts` already exists (migration 0008).

### Replacing the 0.8

0.8 came from `docs/decisions/lane-c-generation.md`: "Floor: 80% Critic confidence (R03.7 Rubik
Pass)". That is a fleet-level target — "80% of drafts should pass" — implemented as a per-draft
decision boundary. Different statements.

Choose each gate's operating point from a labelled validation set, with **different target recalls
per gate**: a missed PII leak and a missed tone mismatch have different costs. Youden's J, or a
target-recall point on a precision-recall curve given class imbalance.

## Also: strip quoted history inside `extract_actions()` only

Email zoning improved request detection from 72.28% to 83.76% accuracy in Lampert, Dale and Paris
(NAACL-HLT 2010) — a 41% error reduction. Our extraction produced false positives from quoted
history and from already-resolved threads.

**Scope constraint:** strip for extraction only. Quoted history is legitimate context for
*generation* and removing it globally would degrade drafts. Candidate libraries: `talon`,
`email-reply-parser` — both new dependencies, so ask-first.

## Dependencies

- **`extract_actions()` recall bounds Gate 4.** Measured on 20 emails: item recall 12/12, email-level
  precision 0.64. **The intervals are wide** — 95% Wilson on precision is [0.39, 0.84], on item
  recall [0.76, 1.00]. A second batch of 50 is being labelled; until then, treat the direction as
  suggestive and the rates as unestablished.
- Gate 4 also wants an upstream actionability check. Neither the priority classifier nor the
  router's NA decision separates action-needing from no-action emails in our sample.
- Gate 1 needs Presidio reachable from Python. It runs today as a container for Lane A only.

## Acceptance criteria

- [ ] Given a draft containing an unmasked email address or NRIC, when Gate 1 runs, then
      `needs_human_review` is true and the offending span is recorded.
- [ ] Given a draft asserting a figure absent from the retrieved context, when Gate 2's specifics
      check runs, then the draft is flagged and the unsupported value named.
- [ ] Given a tone mismatch and no other failure, when the gates run, then the draft is **not**
      blocked and the tone score is surfaced to the reviewer.
- [ ] Given a draft that needed one or more refine rounds, when the gates run, then
      `needs_human_review` is true regardless of final confidence.
- [ ] Given any evaluated draft, when the row is inspected, then each gate's individual result is
      persisted, not just a scalar.
- [ ] Given an NA-category message, when it is stored, then `critic_confidence` is NULL, not 0.0.

## Open questions

- Pin temperature and model version? Worth doing for reproducibility, but **temperature 0 does not
  guarantee determinism** — batch-size-dependent reduction kernels and floating-point
  non-associativity remain. Pin it and report residual nondeterminism as a limitation rather than
  claiming reproducibility.
- Fix `dashboard.py:120`'s `or 0.0` in this change or separately? Two lines of code, but the ten
  existing rows need backfilling to NULL and `:124` formats with `:.2f`, which throws on None.
- Gate 2's verifier: local NLI model (adds torch to the API process) or a separate LLM call from a
  **different model family** than the Gemini drafter?

## Sequencing

This must not displace prompt-injection fencing. Both restructure `email_agent.py`, so they should
land in one sequence rather than competing. Suggested order, cheapest first:

1. ~~`attempts > 0` in the review condition~~ — done
2. ~~Split the refine and review thresholds~~ — done (refine 0.8, review 0.9)
3. ~~Persist per-gate results~~ — done (migration 0010, `critic_checks` JSONB)
4. ~~Gate 1 deterministic PII~~ — done, verified live against the running analyzer
5. ~~Gate 3 demoted to advisory~~ — done
6. ~~Gate 4 per-item coverage~~ — done, and it costs no extra API call: the extracted requests
   are passed into the critic call that already runs. Its *trustworthiness* still depends on
   `extract_actions()` recall, whose interval remains [0.39, 0.84].
7. Gate 2 — **half done.** The deterministic specifics check is in. Claim decomposition plus
   entailment is deferred; revisit on reproducibility grounds once the project is on paid API
   access, since quota is no longer the deciding factor.

## Verification notes

Several citations above were surfaced by a literature review rather than read from primary PDFs.
Before quoting any of them in the report: verify RAGAS's current metric definition (the legacy
`Faithfulness` API is deprecating), check the installed Presidio version's `supported_entities`, and
do not quote Youden's 1950 paper verbatim — the formula is universally attributed but the phrasing
circulates via secondary summaries.

## Decisions

- 2026-09-11: the review gate reads the four checks, not the scalar. Rationale: the scalar has no
  definition and is documented to saturate; the four booleans are concrete and already computed.
  Alternatives: recalibrate the threshold, which we can do but which leaves the gate reading a
  number nobody can defend.
- 2026-09-11: tone is advisory. Rationale: subjective, noisy to measure, low downstream risk given
  human approval. Alternatives: keep it as a gate, which blocks good drafts on style.
