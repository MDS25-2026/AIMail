# Final sprint plan — to 2026-10-13

Every open item across all four lanes, sequenced. Written 2026-09-17, four weeks out.

Sources consolidated here: the nine audit items
([`audit-remediation-plan.md`](audit-remediation-plan.md)), the feature backlog
([`backlog.md`](backlog.md)), and the defect list ([`known-issues.md`](known-issues.md)). Every item
now has a GitHub issue on milestone **Week 10 — final submission**, nested under its epic.

**Scope decision:** all four lanes, content and demo both. Nothing is being carried as "documented
but unbuilt" unless this file says so explicitly.

## The honest position on scope

Thirty-two open issues in four weeks, with the Chrome extension (L) and attachment OCR (M) both
unstarted. Cut lines are marked below rather than discovered in the last week. An item below the
cut line that gets designed and written up is worth more than one half-built.

## Critical path

The P0 chain is short, and nothing else should displace it.

```
#87  user study  ────────────────┬──> #78  critic validation (Part 2, same session)
     (calendar lead time)        └──> #90  sender list (gated on findings)

#74  injection spec ──> #71  port fencing onto main ──> #75  harden the helper
                                    │                   #76  fence /refine
                                    └──────────────────> #79  user profile

#80  mask uploaded documents ──> #99  index sent mail

#92  ADR 0003 ──> #94  MV3 shell ──> #95  content script
#93  D3 live container (independent — do this first, it is the demo fallback)
```

**#87 starts today.** It is the only item whose duration is set by other people's calendars.
Everything else can be compressed; recruitment cannot.

## Week by week

### Week 1 — to 2026-09-24

| Issue | Item | Lane |
|-------|------|------|
| #87 | Build and pilot the study instrument, begin recruiting | B |
| #74 | Write the prompt-injection defence spec | B (for C) |
| #71 | Port the fencing onto main, with tests | B (for C) |
| #80 | Mask uploaded documents | B |
| #93 | Extension D3 — live container | D |
| #92 | ADR 0003 | D + team |

Rationale: the study's clock starts. Fencing is the audit's highest-severity open item and the one
the board wrongly showed as done. Upload masking contradicts the project's central privacy claim.
D3 is the extension's de-risking step — if D4 and D5 are cut, D3 alone still leaves a working demo.

### Week 2 — to 2026-10-01

| Issue | Item | Lane |
|-------|------|------|
| #103 | Label batch 2, recompute extraction recall | B |
| #75, #76 | Harden the fence helper, fence `/refine` | B |
| #91 | Reproducible training and evaluation data | B |
| #88 | Priority backfill | B |
| #82 | Attachment OCR | A |
| #94 | Extension D4 — MV3 shell | D |
| #83, #84, #85 | Ingestion reliability defects | A |

### Week 3 — to 2026-10-08

| Issue | Item | Lane |
|-------|------|------|
| #78 | Critic validation against study responses | B |
| #89 | Signature role assessment | B |
| #95 | Extension D5 — content script (timeboxed) | D |
| #96, #97 | Scroll fix, inbox sort | D |
| #100, #101 | Archive legacy, AI_DOCS entries | all |
| #77, #86 | Subject line, insert timeout | C, A |

### Week 4 — to 2026-10-13

Writing up, rehearsal, and only the items below that have actually landed. **No new work starts in
week 4.** Anything not begun by 2026-10-08 moves to the documented-not-built list.

## Cut line

If time runs short, drop in this order. Each of these is more valuable written up as designed
methodology than half-implemented.

1. **#99 index sent mail** — the largest item on any list, and it competes directly with the
   extension and fencing for the same weeks. The blind-eval design is a legitimate report
   contribution unrun.
2. **#98 live Gmail body fetch** — deliberately scheduled after the pitch. The current demo
   narrative uses the masked copy as the privacy proof; changing that mid-week undercuts a
   rehearsed story for no marking gain.
3. **#90 sender priority list** — gated on study findings anyway.
4. **#81 masking transparency panel** — good value, but needs Lane A and Lane D in sequence.
5. **#102 dashboard flatten** — pure hygiene; must either happen before #94 or not at all.
6. **#95 extension content script** — the unknown-cost piece. Gmail DOM detection is the part
   nobody can estimate. Fallback is the `/extension` route from #93.
7. **#104 deadline extraction evaluation** — epic #16 has no evidence behind it, but the
   classifier work is the stronger story.

**Never cut:** #87, #71, #74, #80, #78. Those five are the difference between claims that are
defensible and claims that are not.

## Lane D is the constraint

Issues #81, #97, #98 and #90 all need Lane D time, and Lane D also owns the extension — Goal 1 of
the proposal and the largest gap between what was promised and what exists.

**Nothing displaces the extension.** If Lane D capacity binds, the order is: #93, #92, #94, #95,
then #96, then #97, then #81, then #98.

#87 needs almost no Lane D time at all, which is another reason it goes first.

## Standing constraints

Carried forward because they have each caused a failure that looked like something else:

- Stop `make dev` with Ctrl+C, never Ctrl+Z. A suspended run keeps holding ports and subscriptions.
- DNS resolves only through Tailscale, so a blip fails everything at once and looks like ten bugs.
- The migration runner splits on `;` and only strips full-line comments — never put a semicolon
  inside an inline SQL comment.
- Spec before code, including for small features. Tiny features get tiny specs.

## Caveats that must survive into the report

These are true today and must not be quietly rounded up as work lands:

- The masking fixture was written **after** the implementation. 38/38 means "no known failure mode
  is unhandled", not "masking is complete".
- Critic confidence is self-reported and has never been validated against human judgement — until
  #78 closes, no claim about it is supported.
- Uploaded documents bypass masking entirely until #80 lands.
- The classifier's 0.69 sits inside roughly ±9% on 120 samples, and has no human-agreement ceiling
  to be read against until #87 reports.
- `extract_actions()` recall is [0.76, 1.00] and precision [0.39, 0.84] on n=20. Wide enough that
  the direction is suggestive and the rates are unestablished.
- Temperature is pinned at 0, which reduces sampling randomness but does **not** guarantee
  determinism — batch-dependent reduction kernels vary run to run regardless.
