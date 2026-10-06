---
name: pre-pr
description: Use before opening a pull request in AImail. Runs the judgment review (spec match, cross-file consistency, scope, lane boundaries), delegates the deterministic checks to `make check`, then opens a Conventional-Commit PR into main. Invoke when a change is ready to ship.
---

Gate a change before it reaches protected `main`. Do the reasoning parts yourself; delegate deterministic checks to the task runner. Report each step's result, including negatives.

1. **Spec match** - re-read the feature's spec. Does the change do what was asked, with no scope creep? State the result.
2. **Cross-file consistency** (mandatory):
   - README drift: for every touched directory with a README, re-read it and confirm it still describes the code. Update if stale.
   - `.env.example` drift: any new env var / URL / key name introduced? Add it (name + comment only, never the value).
   - utils extraction: did you write a near-twin of an existing helper? Grep the repo; extract if a twin exists.
3. **Lane boundaries** - did the change touch another lane's folder or a shared contract? If so it must be reflected in `specs/context/` and logged in `docs/decisions/shared.md`, and flagged for the owner's review. (The `lane-check` skill does this analysis.)
4. **Deterministic checks** - run `make check` (backend tests + lint + frontend typecheck). Do not proceed if it fails; fix the cause, never delete or skip a test to pass.
5. **Open the PR** - Conventional Commits title, `Fixes #<issue>` footer, base `main`. Summarise the change and the consistency results in the body.

Report each step explicitly, e.g. "README in backend/ checked - still accurate."
