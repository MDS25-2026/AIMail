# Priority calibration and critic validation user study

- **Status:** draft
- **Owner:** @veyroxie
- **Related issue:** #
- **Last updated:** 2026-09-09

## Goal

Put measured numbers behind the project's two weakest claims in one participant session: give the
classifier's 0.69 macro-F1 a human ceiling to be read against, and test whether the critic's
self-reported confidence tracks human judgement of draft quality.

## User story

As the team defending this system in a report and viva, I want the priority rubric and the critic
threshold checked against real people, so that "0.69" and "below 0.8 is flagged" stop being
unanchored numbers.

## Scope

**In scope**
- A single instrument with a consent screen, a job-role question, and two rating parts.
- **Part 1 — priority sorting.** 9 unmasked emails drawn from the existing 120-email human-labelled
  holdout (`backend/holdout_to_label.csv`), sorted into low / medium / high, with a free-text reason
  requested on 2-3 of them.
- Two closing questions: did any email fail to fit the three tiers, and would a list of important
  senders have changed the sorting (this one gates backlog item 6b).
- **Part 2 — critic validation.** ~20 already-generated drafts rated good / bad, sampled to span the
  `critic_confidence` range on both sides of 0.8.
- An analysis plan fixed **before** collection, and a results write-up.

**Out of scope**
- Any change to the classifier, its training data, or its evaluation. The model is the thing being
  measured; touching it invalidates the measurement.
- Building the sender-priority list (backlog 6b). This study decides whether to build it.
- Changing the 0.8 review threshold. The study measures the threshold; moving it is a later call.
- Generating new drafts for Part 2. It rates what already exists.

## Acceptance criteria

- [ ] Given the instrument, when a participant opens it, then a consent screen precedes any study
      content, and no study item is visible until consent is recorded.
- [ ] Given the 9 Part-1 items, when the selection is reviewed against the rubric, then each of the
      four boundary rules (availability-with-no-ask, FYI-with-no-request, request-in-an-older-thread-message,
      social-with-a-minor-ask) is exercised by at least one item, and at least two items are
      unambiguous anchors.
- [ ] Given the 9 Part-1 items, when their source is checked, then every one is a row of
      `holdout_to_label.csv` with its existing gold label recorded, so participant labels are
      comparable to both the gold labels and the model's predictions on the same text.
- [ ] Given N completed responses, when the analysis runs, then it reports (a) per-participant
      macro-F1 against the holdout gold on those 9 items, (b) inter-participant agreement across all
      participants, and (c) the model's macro-F1 on the same 9 items — all three from the same items.
- [ ] Given the ~20 Part-2 drafts, when the sample is checked, then at least 5 sit below
      `critic_confidence` 0.8 and at least 5 at or above it, so the threshold is testable rather than
      assumed.
- [ ] Given N completed responses, when the Part-2 analysis runs, then it reports how often the 0.8
      threshold agreed with the human good/bad verdict, as a 2x2 with all four cells populated.
- [ ] Given any stored response, when it is inspected, then it carries a sequential participant ID
      and a job role, and no name, email address, or other participant identifier.
- [ ] Given the reported numbers, when they appear in the report, then each is stated with its
      participant count and item count alongside it.

## Part 1 item selection (chosen 2026-09-12)

Row indices into `backend/holdout_to_label.csv`. Recorded so the model's predictions on exactly
these items can be recomputed; the corpus file is gitignored, the indices are not.

| Row | Gold | Model | Conf | Why this item |
|-----|------|-------|------|---------------|
| 3 | high | high | 0.86 | **Anchor.** "I would like to have a copy of the appraisal." Unambiguous direct request. |
| 8 | high | *medium* | 0.69 | **Anchor**, and the model under-escalates it. "Please forward this note... It must be sent by you." |
| 17 | medium | medium | 0.69 | **Boundary: FYI / attached-please-find with no request.** Closes with "if you have any questions, please call". |
| 53 | low | low | 0.84 | **Boundary: mostly-social with one minor ask.** "Happy B-day punk... if you are, shoot me a line." See the rubric tension below. |
| 64 | low | low | 0.93 | **Anchor.** Pure marketing — "claim your gift", "click here now". |
| 77 | medium | medium | 0.88 | **Boundary: soft review request.** "The draft for your review and comments, as promised." Is being asked to review a document a request or an FYI? |
| 91 | high | high | 0.55 | **Boundary: request buried in quoted history.** New text is only "FYI - Lets talk about this today"; the substance sits in the forwarded RFP below. Lowest model confidence in the set. |
| 110 | low | *high* | 0.83 | **Boundary: automated mail that genuinely requires action.** Subject is literally "Action Requested: Invoice Requires Coding/Issue Resolution/Approval", forwarded with "Ava, have you taken care of this?". Human said LOW on the automated signal; the model said HIGH, confidently. |
| 2 | medium | medium | 0.75 | **Boundary: several soft requests.** "It would be useful to share this", "I'd like to see...", "Let's talk." A human read all three as MEDIUM rather than HIGH. |

Gold spread 3 low / 3 medium / 3 high. Deliberately not representative of the holdout's
46/46/28 — the instrument tests the boundary rules, and a proportional draw would return
mostly easy cases.

The model agrees with the human gold on 7 of 9. That is not a performance claim: these items
were chosen to be hard or diagnostic, so the number is not comparable to the 0.69 macro-F1.

### Two findings from the selection itself

**No availability/scheduling email exists in the holdout.** The rubric's first boundary rule
("I'm free Tuesday", with no explicit request to book, resolves to MEDIUM) has no instance in
120 emails — a targeted search for first-person availability language returned nothing usable.
That rule therefore cannot be tested with items comparable to the 0.69. Either drop it from the
study, or add one non-holdout item explicitly marked as not comparable. Recommend dropping it
and reporting the absence.

**Row 53 contradicts the written rubric.** The rubric says mostly-social-with-one-minor-ask
resolves to MEDIUM; the human labelled this one LOW. Both readings are defensible — the ask is
very minor — but the gold set and the written rule disagree, which is worth putting to
participants rather than quietly resolving. It is also a caution about the rubric's own
consistency, the same issue that capped the classifier before the relabelling.

## API surface

None. No endpoint, no service change. The deliverable is an instrument, a response set, and an
analysis script under `backend/scripts/`.

## Data model

No migration. Reads `holdout_to_label.csv` (already on disk, gitignored) and, for Part 2, existing
`messages.draft_reply` + `messages.critic_confidence` (migration `0004_message_generation.sql`).

Responses are stored as an anonymised CSV outside version control, consistent with the existing
data policy that keeps `backend/*.csv` gitignored.

## Dependencies

- `backend/holdout_to_label.csv` — 120 rows, all labelled, distribution 46 low / 46 medium / 28 high.
  Verified present 2026-09-09.
- **Unverified precondition:** at least ~20 messages carrying both a `draft_reply` and a
  `critic_confidence`, spanning both sides of 0.8. `known-issues.md` records only 32 messages total,
  so this is not guaranteed. Must be confirmed with a query before Part 2 is written.
- Ethics: the unit's position on human-participant research in FIT3164 is not recorded anywhere in
  this repo. A consent screen is in scope regardless; whether institutional clearance is also
  required is an open question below.
- Cross-lane: Part 2 measures Lane C's critic. No Lane C code changes, but the finding lands on
  Hanif's lane and belongs in `docs/decisions/shared.md` once results exist.

## Edge cases & failure modes

- **Too few participants.** 9 items times a handful of people is a small sample. Mitigation is
  honesty, not more statistics: report N with every figure. Below 4 participants, report agreement
  descriptively and drop the macro-F1 comparison rather than publish a number built on ~27 judgements.
- **Participants who do not resemble the target population.** The corpus is workplace email and the
  classifier is for workplace triage, so a ceiling measured entirely on people who have never
  managed a work inbox is a ceiling for the wrong population. This is the study's main threat to
  validity and it cannot be fixed by statistics.
  Mitigation, in order of preference: recruit at least two or three people who currently handle
  work email; record the experience spread either way; and report the composition alongside every
  figure. If the sample skews inexperienced, say so and scope the claim to "how people unfamiliar
  with corporate mail sort it", which is still a finding — it just is not the finding the report
  would otherwise imply.
- **All Part-2 drafts score above 0.8.** Then the threshold cannot be tested at all. Detect this at
  sampling time, before recruiting; if it holds, Part 2 becomes "does confidence correlate with
  quality at all" and the threshold question is deferred with the reason recorded.
- **A participant abandons midway.** Part 1 is complete on its own; keep partial responses that
  finished Part 1 and record them as Part-1-only.
- **Participants disagree with the gold labels as a group.** That is a finding, not a failure — it
  says the rubric does not match how people sort, which is one of the four questions being asked.

## Security & privacy notes

- Participants see **unmasked** Enron email text. Accepted deliberately: the corpus is public, and
  masked text would no longer be the text the 0.69 was measured on, breaking the comparison that is
  the point of the study. Already noted for ethics in
  [`priority-classifier.md`](priority-classifier.md).
- Part 2 shows generated drafts, which are written from **masked** email content, so no unmasked
  project mailbox content is exposed.
- **No personal data is collected, by design.** Work category is a fixed five-option list, not
  free text: a free-text role is the one field where a participant can identify themselves, and
  one response reading "FYP supervisor for MDS25" would collapse the anonymity claim for the whole
  study. No names, no email addresses, no ID numbers. This is what makes "follow Malaysian law"
  cheap to satisfy — PDPA's obligations attach to personal data, and there is none here.
- Raw responses are deleted once the report is submitted, and the consent screen says so.
- Response data is gitignored like the rest of `backend/*.csv`. Aggregate figures go in the report;
  raw responses do not go in the repo.

## Open questions

All four resolved 2026-09-17. Kept here with their answers rather than deleted, since the reasoning
is what the report needs.

- ~~Ethics clearance beyond the consent screen?~~ **Dr. Asad: follow Malaysian law.** PDPA
  obligations attach to personal data, so the instrument is designed to collect none — see Security
  & privacy below. Recruitment is unblocked.
- ~~Which agreement statistic?~~ **Fleiss' kappa**, for consistency with the Cohen's kappa in
  `label_agreement.py`. Implemented in `scripts/analyse_study.py` rather than adding statsmodels;
  the ordinal caveat prints alongside the number.
- ~~Delivery?~~ **Microsoft Forms.** Institutional tooling, so response storage has a cleaner
  answer under PDPA than Google Forms, at identical effort. A dashboard page was rejected: it is
  the only option costing Lane D time, which is the project's named constraint.
- ~~Target participant count?~~ **Target 8, floor 5.** Below 4, `analyse_study.py` withholds
  macro-F1 and reports agreement descriptively, per the edge case above. Recruit beyond target,
  because people drop out.

## The 0.8 threshold cannot be tested on stored drafts

Found 2026-09-17 while building Part 2, and it supersedes the "all Part-2 drafts score above 0.8"
edge case with a sharper reason.

After regenerating all 18 stored drafts through the current pipeline, **zero fall below 0.8** — and
this is structural, not a sampling accident. `REFINE_THRESHOLD` is 0.8, so the refine loop runs
until confidence clears 0.8. Nothing below 0.8 can survive to be stored, by construction.

Testing the threshold would require capturing **pre-refine** confidence, which is not persisted
today. Part 2 therefore asks whether confidence discriminates at all, which the post-regeneration
spread makes answerable: four distinct values (0.80, 0.85, 0.95, 1.00) where there were two.

Reporting this reason is worth more than reporting "insufficient data", and it is a concrete
follow-up: persist the initial evaluation alongside the final one.

## Out-of-scope future extensions

- Enlarging the 120-email holdout for a tighter confidence interval on the 0.69 itself
  (`known-issues.md`). Related, but a labelling job, not a study.
- Repeating Part 1 on masked text to measure what masking costs a human sorter. Interesting, and a
  second session's worth of work.

## Instrument design decisions (2026-09-17)

**The nine items are not normalised to a common format.** They vary considerably, measured:

| | has From/To/Subject or forwarding | bare body |
|---|---|---|
| items | 4 | 5 |
| gold high / medium / low | 2 / 1 / 1 | 1 / 2 / 2 |

Length varies more than format does — 94 to 2,267 characters, a 24x range.

Format does not track the gold label in any obvious way, though at n=9 that is a weak check and
should not be reported as evidence of no confound.

**Left as-is deliberately.** The classifier was measured on exactly this text, headers included.
Normalising would mean participants judge different information than the model had — sender and
subject are real urgency signals — and the human ceiling would stop being a ceiling for this
classifier. Same reasoning as showing unmasked text.

What is addressed instead is the participant's reaction: the Part 1 intro now says the emails come
from a real archive, will look inconsistent, and that a missing sender is part of the situation
rather than a broken form. Manage the expectation, do not alter the stimulus.

**Report this as a limitation.** Presentation heterogeneity is uncontrolled variance in a 9-item
instrument, and some disagreement between participants will come from it rather than from genuine
differences in judgement.

**Email text is re-flowed before display.** The corpus is hard-wrapped at roughly 70 characters by
a 2000-era mail client. Microsoft Forms discards single line breaks on paste and keeps blank ones,
so raw text arrives as a run-on block — "Thanks in advance.Mick Walters3-4783EB3299d" — with header
lines and signatures fused into the body.

`readable_email()` joins lines that were clearly wrapped (long, no terminal punctuation, not a mail
header) and separates every remaining logical line with a blank line, which is what Forms preserves.

**Not a comparability problem:** no word changes, only whitespace. The classifier's tokeniser
normalises whitespace anyway, so participants read the same content the model was measured on. This
is a different case from masking, which would change content.

**Participants are given no definition of high, medium or low.** An earlier draft included a
"rough guide" defining the three tiers. It was removed, for two reasons.

It would have contaminated the question the study exists to ask. "Does the rubric match how people
actually sort?" cannot be answered after handing people the rubric — that measures whether they can
follow instructions. The same applies to "did any email not fit three tiers": a participant shown
definitions will fit emails to them.

And unguided sorting is the comparison that reflects deployment. The classifier runs against a
user's inbox, and that user has no rubric. A ceiling measured on rubric-following humans would be a
ceiling for a task nobody performs.

**Consequence to report, not to fix:** the gold labels were produced with an explicit boundary
rubric — that relabelling is what moved the classifier from 0.57 to 0.69 — while participants sort
without one. Some participant disagreement is therefore definitional rather than genuine judgement
difference. State this alongside the agreement figure. It cannot be removed without reintroducing
the contamination above, so it is a limitation, not a defect.

**Reasoning is collected on three items, not nine.** `backlog.md` specifies "sort, then explain two
or three". Asking on all nine would triple completion time for diminishing returns. The three chosen
are where disagreement is most informative: the item whose gold label contradicts the written rubric,
the one hiding its request in quoted history, and the one the model got confidently wrong. Without
these, the study yields "humans agree N%" but never why — and the why is the better finding.

**Part 2 asks the four gates separately, not one overall verdict.** Required by #78: a holistic
"would you send this" cannot say which gate carries signal and which is noise. Each draft gets four
plain-language checks mapping to `grounding_ok`, `pii_clean`, `tone_match` and `completeness`, then
an overall verdict. The internal names are never shown — asking "is grounding_ok" gets a shrug.

**Six drafts, not all fifteen.** Four gate questions each, so the count drives completion time.
The sample reserves unflagged controls *first*, then fills on distinct flag reasons: a sample with
no clean draft cannot distinguish a participant who says "fine" to everything from a critic that
flags nothing. Current draw is 2 clean plus 4 flagged on distinct grounds.

**"Not sure" counts as no complaint** in the analysis. Treating uncertainty as a gate failure would
inflate every disagreement and make the critic look worse than the evidence supports.

## Implementation notes

Item selection for Part 1 is the real work and should be done by reading candidates, not sampling
randomly: the boundary rules are the point, and a random draw of 9 from a 46/46/28 distribution will
mostly return easy cases. Record the chosen row indices so the model's predictions on exactly those
9 can be recomputed.

Likely files: a selection script and an analysis script under `backend/scripts/`, alongside the
existing `label_agreement.py` and `eval_classifier.py`, whose conventions they should follow.

## Decisions

- 2026-09-09: Part-1 items are drawn from the existing labelled holdout rather than a fresh sample.
  Rationale: only shared items let human agreement, gold labels, and the model's 0.69 be compared on
  the same text. Alternatives: a fresh sample, which yields a second unanchored number.
- 2026-09-09: participants see unmasked text. Rationale: the corpus is public and the 0.69 was
  measured on unmasked text. Alternatives: masked text, which matches production input but breaks
  comparability with every reported figure.
- 2026-09-09: critic validation is bundled into the same session rather than run separately.
  Rationale: both need participants, and recruiting once is the whole saving; the team minutes of
  2026-09-04 already pair urgency labelling with critique criteria. Alternatives: two studies, which
  doubles recruitment for the project's scarcest resource.

## Protected decisions

<!-- BEGIN PROTECTED -->
The classifier, its training data, and its evaluation set must not be modified while this study is
open. The study's entire value is that it measures the 0.69 as it currently stands; retraining or
relabelling mid-study makes the human ceiling incomparable to the model number it exists to anchor.
DO NOT change this without explicit approval from the Lane B owner.
<!-- END PROTECTED -->
