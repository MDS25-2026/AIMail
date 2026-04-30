# AI-assisted development workflow

How we use Claude Code, Lovable, or any LLM to actually build features on AImail. Methodology adapted from the team meeting on 2026-04-27 (supervisor + Alim).

The TL;DR: **AI is good at lying.** Build through verification loops, not through faith.

---

## The loop

```
1. Voice/draft a prompt   →   2. Proofread the prompt   →   3. Gap analysis (×10–20)   →   4. Implement   →   5. Verify
```

Each stage has a job; skipping any of them is what produces 40% bug rates.

---

## Stage 1 — Voice or draft the prompt

Get the requirement out of your head into text. Speed > polish.

- Speak it (voice memo → transcribe) or type it. Don't pre-edit.
- Include: **what** you want, **why**, **constraints** (language, framework, conventions), and **what good looks like**.
- Reference the relevant spec in `specs/features/` if one exists.
- Reference [`../specs/conventions.md`](../specs/conventions.md) for code style — don't restate it, link it.

If your prompt is shorter than the feature spec, your prompt is too thin.

---

## Stage 2 — Proofread the prompt

Before sending the prompt to a build LLM, send it to a **different** LLM with a proofreading instruction. Goal: tighten language, strip ums, surface ambiguities the LLM will silently guess on.

A working proofreading prompt template:

```
Do not act on the following request — only proofread it.
Tighten language, surface ambiguities the executor will guess on, and
preserve all technical detail. Output the cleaned prompt only, no commentary.

REQUEST:
<paste your stage-1 prompt here>
```

Output of stage 2 is what goes to stage 3.

---

## Stage 3 — Gap analysis (the load-bearing step)

This is where 80% of the quality comes from, and where most teams skip.

For each iteration:

1. Send the prompt to an LLM with this question:
   *"If you were asked to implement this exactly as written, what percentage of the requirements would you fulfill correctly? List the specific gaps, ambiguities, and likely-wrong assumptions."*
2. The LLM gives a number (e.g. "60%") and a list of gaps.
3. **Update the prompt to fix every gap.** Don't just answer them in chat — bake them into the spec.
4. Re-run the question. Number should rise.
5. Repeat until the LLM consistently says ~100% with no remaining gaps. Usually **10–20 iterations**.

**Only after gap analysis converges do you implement.** Even then, expect 40–60% correct on first build.

---

## Stage 4 — Implement

Hand the gap-analysed prompt to your build LLM (Claude Code, Lovable, etc.).

- Implement in **one focused PR** — don't bundle unrelated work.
- Run linters / type-checkers / tests as you go (see [`../specs/conventions.md`](../specs/conventions.md)).
- If the LLM goes off-script, **stop and re-prompt** rather than letting it improvise. A drifting LLM is a sunk-cost trap.
- Functions ≤15 lines, no `any` / `unknown` outside validation boundaries, all the rules in conventions.md still apply.

---

## Stage 5 — Verify

Treat AI output as a contractor's first draft.

- Re-read every changed file in context of its callers, not just the diff.
- Walk a test matrix: happy path, empty input, null, boundary values, malformed input, concurrency.
- Scan for the AI failure modes (full list in `~/CLAUDE.md`):
  - Hallucinated imports / methods / object properties
  - Off-by-one and null-handling
  - Silent semantic errors (compiles, runs, wrong result)
  - Loose equality where strict is needed
  - Empty `catch` blocks, swallowed errors
  - String concatenation into SQL
  - Deprecated API usage
  - PII / secrets in error messages
- Run linters and tests. **Two consecutive clean passes** before declaring done.

---

## Worked-example: the Chrome extension demo

In the 2026-04-27 meeting, Alim built a working Chrome extension scaffold in ~30 minutes by following stages 1–4 once. He explicitly noted:

- He skipped most of stage 3 because it was a demo. In real work he runs gap analysis 10–20 times.
- The output was "40–60% correct" — useful as a starting skeleton, not as shippable code.
- Real shipping requires every stage 5 verification pass.

Treat the demo as proof of how *fast* the skeleton can be — not as proof that the loop is optional.

---

## When to use this vs. just typing code

| Scenario                                              | Use the loop? |
|-------------------------------------------------------|---------------|
| New feature, multi-file change                        | Yes           |
| New service or new component                          | Yes           |
| Bug fix in a known function                           | Skip — just fix it |
| Refactor with clear scope                             | Optional      |
| Spike / research / throwaway prototype                | Skip          |
| Anything touching auth, money, PII masking, secrets   | **Always yes** — non-negotiable |

---

## Tooling notes

- **Voice transcription:** macOS dictation, or any phone voice memo + transcription tool.
- **Proofreading LLM:** any model different from your build LLM. The point is independent perspective.
- **Gap-analysis LLM:** same model as build LLM is fine — its self-audit is still useful.
- **Build LLM:** Claude Code (CLI in this repo), Lovable (web), or whatever the team picks. Pin per-feature in the spec.

---

## Status

**Status:** active.
**Last reviewed:** 2026-04-29.
