# Normalisation v2, stage 4: translation last, then one reprocessing run

- **Status:** ready to build (2026-10-18)
- **Owner:** veyroxie (spec); builder: a teammate while veyroxie's GitHub account is under review
- **Related:** `normalisation-v2.md`, `normalisation-v2-stage3.md`
- **Depends on:** stages 2 and 3 merged
- **Estimate:** about half a day, plus the reprocessing run

## Goal

Stages 2 and 3 make every step read English. Stage 4 makes sure what the reader and the sender see is in
the right language: replies in the sender's language, and an instant "Translate to English" from the
stored copy. Then one run applies the new masking, the normalisation and the English copy to the mail
already stored.

## Task 1: replies in the sender's language (3 h)

**Background:** the agent already writes in the email's language (`_LANGUAGE_RULE` in
`email_agent.py`: "Write the reply in the same language as the email_body"). Gemini does this well.
Gemma, the local model in Private mode, answered Malay emails in English until that rule was added, and
is still weaker at Malay (`specs/features/local-model.md`).

**Agent** (`email_agent.py`; Hanif to review):
1. `ProcessEmailRequest` gains `reply_language: str = ""` (`en`, `ms`, `zh`, from `messages.language`).
   When it is set, `_LANGUAGE_RULE` names it ("Write the reply in Malay.") instead of "the same
   language as the email_body", which a mixed email made ambiguous.
2. **Gemini:** writes directly in `reply_language`.
3. **Local provider, and `reply_language` is not `en`:**
   - draft in English, using the English copy from stage 3;
   - then call the existing translate step into `reply_language`;
   - if the translation is refused as unfaithful, keep the English draft and set a review reason
     `reply_not_translated`, so the reader sees why and can Translate or rewrite it.

**Backend:** send `reply_language=message.language or ""` in `_generate` and `_refine`.

**Tests:**
- **Gemini path:** the prompt names the reply language.
- **Local path:** an English draft is translated, and a refused translation leaves the English draft with
  the review reason.
- **Backend:** the request carries the email's language.

## Task 2: "Translate to English" reads the stored copy (1 h)

**Backend:** `DashboardEmail` gains `subjectEn` and `ownTextEn` (detail view only, not list rows, to keep
the inbox light). Additive contract change.

**Frontend** (`src/components/EmailBody.tsx`; Han to review):
- when the reader asks for English and `ownTextEn` is present, show it straight away, with no request,
  and the notice "Translated by AI from the masked text";
- other target languages keep calling `/emails/{id}/translate` as now.

**Tests:**
- **The stored copy:** asking for English shows it without a request.
- **No copy:** asking for Malay still calls the backend.

## Task 3: one reprocessing run (the owner, after stages 2 to 4 are deployed)

The listener command already exists (`go run . reprocess`, `specs/features/readable-emails.md`). Since
stage 2 it also clears `language`, `subject_en` and `own_text_en`, so the worker normalises each email
again with the new masking.

1. Wait until Render has deployed stages 2 to 4. Check `/status`.
2. From `listener/`, with the shared `.env`:
   - **Dry run:** `go run . reprocess`, which prints how many emails would change.
   - **The owner decides.** Unsent drafts are written again, so edits to them are lost.
   - **Then:** `go run . reprocess --write`.
3. Watch the worker logs: `normalise:` counts go up as the backlog drains (20 emails every 30 s).
4. **Spot-check three emails, with numbers only, never content:**
   - a Malay one has `language = ms` and an English copy;
   - an English one has `language = en` and no copy;
   - one with "by Friday" has `deadline_at` set.

The run needs only database access, not GitHub, so veyroxie can run it from their laptop.

## Task 4: measure it, for the poster (2 h, can run on 20 to 21 Oct)

- **Pick 30 real emails** (masked text only) across the three languages.
- **Label each one by hand** with its category and its deadline (or none).
- **Record the results** in `docs/data/normalisation-eval.md`, with the method and the 30 email ids, never
  their content:
  - category accuracy: the agent's category against the trained model's;
  - deadline precision: deadlines found that are right;
  - deadline recall: right deadlines that were found.

## Definition of done

- [ ] **A new migration is run on the live database before the PR merges** (`make migrate` from a laptop
      with the shared `.env`). Render does not run migrations, and code that deploys first breaks every
      email query.
- [ ] `make check` passes with `.env` moved aside. The database tests pass on a fresh database.
- [ ] Contract changes are recorded in `api-contracts.md` and `docs/decisions/shared.md`.
- [ ] Every new string is in en, ms and zh.
- [ ] `normalisation-v2.md` is updated: each stage's status, and what was cut.
