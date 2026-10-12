# Drafting skips: automated emails, Private mode without a private model, and holding-reply fields

- **Status:** built 2026-10-12
- **Found by:** the owner using the hosted app (drafts written for Milanote notifications; "drafting
  service unavailable" on Refine; a holding reply sent as "Hi (name),")

## 1. Automated emails get no automatic draft

- The listener's `is_automated` (mailing-list headers, no-reply senders, auto-replies) only stopped
  holding replies; drafting ignored it, so 30 newsletters and notifications had drafts.
- `refusal_for(message, Action.DRAFT)` now refuses automated emails with `automated_email`, and the
  background drafter's `drafting_filter()` skips them. Regenerate (`Action.REDRAFT`) still drafts one on
  request.
- The listener also counts Gmail's non-primary tabs (`CATEGORY_PROMOTIONS`, `CATEGORY_SOCIAL`,
  `CATEGORY_UPDATES`, `CATEGORY_FORUMS`) as automated: Milanote's mail carried none of the headers.
- The email view says why there is no draft (`isAutomated` on `DashboardEmail`).
- The recipient's-local-time hint is not offered for automated mail, nor for a `+0000` offset, which is
  what mail servers stamp, not where a person is.

## 2. Private mode where this server has no private model

- An account with Private mode on, used on a server without `LOCAL_LLM_MODEL` (the hosted app), had every
  draft, Refine and translation fail as "drafting service unavailable".
- `model_for(user_id)` refuses those calls with `private_model_unavailable`, and the background drafter
  skips such accounts. They are never quietly sent to Gemini: that would break the promise Private mode
  makes. Switching Private mode off in Settings always works.

## 3. Holding-reply fields people actually type

- A template with `(name)` went out unfilled, because only `{name}` was recognised.
- `(name)`, `[name]`, `<name>` and `{{name}}` (any case), and the same for `return_date`, are filled in
  as `{name}`/`{return_date}`.
- A holding reply that still holds a redaction marker or an unfilled `{field}` after filling is cancelled
  (`unfilled_field`), never sent: nobody checks it before it goes.

## 4. Greeting line

- A draft greeted "Hi Mei Ling Chong / Procurement", copying a signature's department. Every drafting
  prompt now says to greet with the name, or its placeholder, only.
