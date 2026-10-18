# Normalisation v2, stage 3: every step reads the English copy

- **Status:** ready to build (2026-10-18)
- **Owner:** veyroxie (spec); builder: a teammate while veyroxie's GitHub account is under review
- **Related:** `normalisation-v2.md` (the plan), stage 2 branch `feat/normalise-stage2`
- **Depends on:** stage 2 merged (`messages.language`, `subject_en`, `own_text_en`, `deadline_at` filled by
  the worker's `normalise` job)
- **Estimate:** about one day, split into the tasks below; each task can be its own PR

## Goal

Stage 2 stores, for every non-English email, an English copy of its subject and of what the sender wrote
(`subject_en`, `own_text_en`), and fills `deadline_at`. Nothing reads them yet. Stage 3 points every step
that judges or answers an email at the English copy, and shows what the new data makes possible: real
categories, due badges, and a Notifications filter.

## The one rule every task follows

Use the English copy when it exists, the original otherwise:

```python
# backend/app/normalise/english.py (new, task 0)
def english_subject(message: Message) -> str:
    return message.subject_en or message.subject or ""

def english_own_text(message: Message) -> str:
    """What the sender wrote, in English when the email had to be translated."""
    return message.own_text_en or own_text(plain_text(message.body_masked or ""))
```

Never send the English copy anywhere the original would not have gone: it is masked text, from the same
vault numbering, so the existing masking and placeholder checks apply unchanged. Do not put real names
back into it.

## Task 0: the two helpers (30 min)

- **File:** `backend/app/normalise/english.py`, with the two functions above.
- **Tests:** `backend/tests/test_normalise_english.py`:
  - an email with `own_text_en` returns it;
  - an English email returns its own text without the quoted part.

## Task 1: categories from the model that drafts (3 h)

**Why:** the trained category model (`app/ml/category.py`) scores 0.26 on average on real mail and
put "client" last on a plain client email; the badge (shown at 0.5 and above) almost never appears.
Gemini got 8 of 9 test emails right and Gemma (Private mode) 8 of 9 (measured 2026-10-13).

**Agent side** (`backend/email_agent.py`, Lane C, Hanif to review):
1. In `route_email`, add a second field to the structured output: `business_category` with
   `enum: ["client", "vendor", "internal", "security", "admin", "personal"]`. Keep `category`
   (STANDARD/COMPLEX/NA) as it is.
2. Add the definitions to the router prompt, from the reader's point of view:
   - **client:** a customer of the reader's company (orders, contracts, requests, complaints).
   - **vendor:** a supplier or service provider (invoices, quotes, deliveries).
   - **internal:** colleagues (meetings, projects, team updates).
   - **security:** account alerts, sign-in warnings, phishing, compliance or audit notices.
   - **admin:** HR, payroll, leave, claims, facilities, policies, logistics.
   - **personal:** family, friends, social plans.
3. `ProcessEmailResponse` gains `business_category: str | None`.
4. `ProcessEmailRequest` gains `email_body_en: str = ""`. When it is not empty, the router reads it
   instead of `email_body`.

**Backend side** (`backend/app/dashboard.py`, `_generate`):
1. Send `email_body_en=details.renumber(str(message.id), message.own_text_en or "")`.
2. When storing the generated fields (`_generation_fields`), set `category` to the agent's
   `business_category` and `category_confidence` to `AGENT_CATEGORY_CONFIDENCE = 0.9`, a named
   constant with a comment: the agent gives no probability; 0.9 means "from the drafting model" and
   clears the badge's 0.5 cutoff.
3. The trained model stays as the fallback for emails that are never drafted. Change
   `app/ml/categorise.py` to skip rows that already have a category. It already only fills NULLs,
   so check that it does not overwrite.

**Tests:**
- **Agent:** a stubbed Gemini answer carrying `business_category: "vendor"` comes back in the response.
- **Backend:** the stored category is the agent's.
- **Backend:** an automated email that is not drafted keeps the trained model's category.

**Contract:** `ProcessEmailRequest` and `ProcessEmailResponse` are internal (backend to agent).
Record them in `specs/context/api-contracts.md` under the agent section anyway.

## Task 2: "Notifications" instead of a category for automated mail (1 h)

- **Frontend** (`src/lib/inboxFilter.ts`, `src/components/CategoryBadge.tsx`; Han to review):
  - when `email.isAutomated`, the badge reads **Notifications** (Bell icon) instead of a category;
  - the inbox filter gains **Notifications**, which keeps the automated emails.
- **Strings:** `category.notifications` in en, ms and zh ("Notifications", "Pemberitahuan", "通知").
- **Tests:** a component test for the badge, and a unit test for the filter.

## Task 3: due badges on To-do rows and in the inbox (2 h)

**Backend:**
- `DashboardEmail` gains `deadlineAt: str | None` (ISO, from `messages.deadline_at`). Set it in
  `_to_email`.
- Additive contract change: record it in `api-contracts.md`.

**Frontend:**
- **The badge** (`src/components/TodoEmailRow.tsx` and `EmailListItem.tsx`), with an icon and words, never colour alone:
  - **Overdue** (danger), when `deadlineAt` is in the past;
  - **Due today** (warning);
  - **Due {weekday}** within 6 days;
  - **Due {d MMM}** after that.
- **Use the reader's time zone** (`useFormat`) to decide "today".
- **Order within a To-do tab** (`backend/app/todo.py`, `by_urgency`): overdue first, then due today, then
  priority, then oldest. Do it in `by_urgency`, so the backend and the page agree.
- **Strings** in en, ms and zh.
- **Tests:**
  - **Backend:** an overdue email sorts first.
  - **Frontend:** each badge state, given a fixed "now".

## Task 4: priority reads the deadline (1 h)

- **File:** `backend/app/personalisation.py`, `apply_policy`.
- **Rule:** after the user's own rules and the automated rule, an email with `deadline_at` within the next
  24 hours is at least **high**, and an overdue unanswered one is **critical**.
- **Named constants:** `DUE_SOON = timedelta(hours=24)`.
- **Leave alone:** SLA rules, which are JJ's (#142).
- **Tests:** due tomorrow is high; overdue is critical; an automated email with a deadline stays low.

## Task 5: drafting, summary, critic and RAG read the English copy (2 h)

- **Summary and action items:** the agent's summariser reads `email_body_en` when it is present.
  Hidden details stay as placeholders, so the dashboard fills them in as now.
- **RAG:** the retrieval query in `_generate` uses `english_own_text(message)`. The policy documents are
  English, so a Malay email finds the right passages.
- **Critic:** pass the English copy as extra context, so the critic judges whether the draft answers what
  was asked. The draft itself is still checked against the original for figures and placeholders.
- **Drafting:** no change in stage 3. The reply language is stage 4.
- **Tests:**
  - the retrieval query for a Malay email is the English copy;
  - the agent request carries `email_body_en` when one exists, and an empty one otherwise.

## Task 6: search finds Malay and Chinese mail by English words (1 h, cut first if short of time)

- **Migration** `0045_search_english.sql`: rebuild the generated `search_vector` to include
  `coalesce(subject_en,'') || ' ' || coalesce(own_text_en,'')`. Check the current definition in
  migration `0035_inbox_search_hybrid.sql`, and keep its weights.
- **Embeddings:** emails are embedded by a script, not the worker
  (`backend/scripts/backfill_message_embeddings.py`; the worker's `embed_pending` embeds document
  chunks). Make the script embed `english_own_text(message)`. Run it again after the stage 4 reprocessing
  run.
- **Test:** a database test where an English search finds a Malay email through its English copy.

## Definition of done (every task)

- [ ] **A new migration is run on the live database before the PR merges** (`make migrate` from a laptop
      with the shared `.env`). Render does not run migrations, and code that deploys first breaks every
      email query.
- [ ] The spec is updated if anything changed while building.
- [ ] `make check` passes with `.env` moved aside (CI has none).
- [ ] The database tests pass on a fresh database. CI runs them.
- [ ] Contract changes are recorded in `specs/context/api-contracts.md` and `docs/decisions/shared.md`.
- [ ] Every new string is in en, ms and zh.
- [ ] The PR names a reviewer: Hanif for the agent, Han for the dashboard, veyroxie for the backend
      (the review comes back over WhatsApp until the account is restored).
