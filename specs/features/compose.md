# Compose: new emails drafted from a brief and the company's own documents

- **Status:** in-progress
- **Owner:** veyroxie (spec, backend, agent); dashboard reviewed by HyperByte12263 (Han)
- **Related issue:** epic #138
- **Last updated:** 2026-10-21

## Goal

AIMail only answered email: there was no way to start one. Compose lets a person write a new email
from a short brief ("tell Keris Logistik we'll raise the credit note by Friday and collect the stock
next week"). The draft is grounded in the policies the company uploaded to Knowledge, so it quotes
the refund window from the refund policy instead of guessing, and the same masking, checks, review
reasons, privacy receipt and human approval as a reply apply before anything is sent.

## User story

As an employee, I want to write a new email by saying what it should say, so that AIMail drafts it
in my style from our own policies, I edit it, and it goes out from my Gmail only when I approve it.
I want to come back to a draft later.

## Scope

**In scope**
- **Saved drafts** (`compose_draft`, migration 0047): recipients (To, Cc), subject, the brief, the
  body, tone, the sources, the critic's verdict and the send state. Kept until sent or deleted.
- **Write with AIMail:** the brief, subject and recipients' display names go to the agent's new
  `/compose` endpoint with the passages `retrieve` finds for the brief. The agent proposes a subject
  when none was typed, writes the body, and runs the same critic, PII scan, figures check and repair
  rounds as a reply, judged against the brief instead of a received email.
- **Refine:** an instruction ("shorter", "mention the 14-day window") through `/compose/refine`.
- **Edit and save:** every field is editable; the page saves as the user types.
- **Send:** Approve & Send with the dashboard's 5-second undo, from the user's Gmail, as a new
  thread (no `Re:`, no threadId). Optional "Remind me if they don't reply" (the To-do waiting list).
- **Compose page** (`/compose`): the user's drafts, newest first, and recently sent ones; the editor.
  A "Compose" entry in the side and bottom navigation.
- **Demo mode:** prepared answers, so "Try the demo" can write and "send" a new email in memory.
- **Privacy text:** `docs/privacy/privacy-notice.md` and the public `public/privacy.html` say that
  AIMail sends new emails the user wrote and approved, not only replies.

**Out of scope**
- Bcc, attachments, scheduling a new email for later, rich text.
- Learning writing style from compose sends (the learner reads reply pairs only).
- Showing compose sends on the Sent page (it lists received emails that were answered); they are
  listed on the Compose page. A unified Sent list is a later change.
- Automatic reconciliation of a send whose outcome is unknown (see Edge cases).

## Privacy model

The rule replies already follow, applied to text the user types:

- **Fixed-format details** the user types (email addresses, phone numbers, IC, passport and card
  numbers) become numbered placeholders (`[PHONE_1]`) **with their values**, kept in the draft's
  sealed vault (`seal_vault`, bound to the owner and `compose:<draft id>`). The draft is stored with
  placeholders, the AI only sees placeholders, and the values are filled in at send. This is
  stricter than Refine on a reply, which masks a new typed number as `[PHONE_REDACTED]` for good;
  that would make a compose draft with a phone number unsendable.
- **Names** the user types are hidden from the model for one request (`TypedNames`, `[PERSON_8xx]`)
  and put back in what comes back, exactly as Refine does. The stored brief and body keep the names.
- **Recipients' addresses** are stored as typed (they are needed to send, like `messages.from_addr`)
  and never reach a model. A recipient's display name ("Harith Zulkifli <harith@…>") becomes a
  placeholder so the draft can greet them by name.
- **The owner's name** is the sign-off placeholder `[PERSON_900]`, as for replies.
- Every prompt is recorded in the privacy receipt (`model_egress.compose_draft_id`).

## Acceptance criteria

- [ ] Given a brief with a phone number, when AIMail writes the draft, then the agent receives
      `[PHONE_1]`, the stored brief holds `[PHONE_1]`, the editor shows the number, and the sent
      email contains the number.
- [ ] Given a brief naming a person, then the agent receives a `[PERSON_8xx]` placeholder and the
      draft shown to the user has the name.
- [ ] Given policies in Knowledge that match the brief, then the draft lists them as Sources and the
      agent's `rag_context` carries them; given none, the review reasons say no document matched.
- [ ] Given an empty subject, then the agent's subject is used; given a typed subject, it is kept.
- [ ] Given a draft whose body the critic finds incomplete against the brief, then repair rounds run
      as for a reply and the review reasons are shown.
- [ ] Given Approve & Send, then the email goes out once as a new thread with To and Cc as typed, a
      `sent_message` row is written (`message_id` NULL), and `compose_sent` is audited with counts.
- [ ] Given two sends of the same draft at once, then only one reaches Gmail; the other gets
      `send_in_progress` or `already_sent`.
- [ ] Given Gmail fails before accepting, then the claim is released and the user can send again.
      Given the outcome is unknown, then the draft is locked as "may have been sent" until the user
      says whether Gmail's Sent folder has it.
- [ ] Given an invalid, CR/LF-carrying or more than 20 recipients, then the API answers 422
      `invalid_recipients` before anything is claimed.
- [ ] Given a body with a placeholder nobody can fill or a redaction marker, then the send is
      refused 422 as for a reply.
- [ ] Given another user's draft id, then every route answers 404.
- [ ] Given Disconnect Gmail or Delete account, then the user's compose drafts are deleted.
- [ ] Given the retention job, then sent drafts go after 30 days (capped by the message content
      limit when set), and unsent drafts follow the message content limit.
- [ ] Given demo mode, then Compose writes, refines and "sends" from prepared answers.
- [ ] Every string in en, ms and zh.

## API surface

`specs/context/api-contracts.md`, "Compose". All routes are the signed-in user's own drafts only.

| Route | Purpose | Limits |
|---|---|---|
| `GET /compose` | Drafts and recently sent, newest first | list |
| `POST /compose` | New draft (any fields may be empty) | at most 200 unsent drafts |
| `GET /compose/{id}` | One draft with its details, sources, review and receipt | detail |
| `PATCH /compose/{id}` | Save edits | refused once sending or sent |
| `DELETE /compose/{id}` | Delete a draft, or a sent one from the list (its masked copy for the waiting list stays); refused while a send may have gone out | |
| `POST /compose/{id}/write` | Write the body from the brief | generation |
| `POST /compose/{id}/refine` | Revise the body per an instruction | generation |
| `POST /compose/{id}/send` | Send the approved fields | send |
| `POST /compose/{id}/outcome` | Settle an unknown outcome: `sent` or `not_sent` | |

## Data model

`compose_draft` (migration 0047): `id`, `user_id` (FK `user_profile`, cascade), `to_addrs TEXT[]`,
`cc_addrs TEXT[]`, `subject`, `brief`, `body` (placeholder form), `pii_vault BYTEA`, `tone`,
`rag_sources JSONB`, `critic_confidence`, `critic_checks JSONB`, `needs_human_review`,
`generated_at`, `send_claimed_at`, `send_outcome_unknown_at`, `sent_at`, `sent_gmail_id`,
`sent_thread_id`, `created_at`, `updated_at`. `model_egress.compose_draft_id` (FK, `SET NULL`).

## Edge cases

- **Outcome unknown:** the claim also sets `send_outcome_unknown_at`, cleared when the send is
  recorded, so a crash between Gmail accepting and the record is never read as "not sent". There is
  no thread to ask Gmail about, so the user settles it: "It was sent" marks the draft sent; "It
  wasn't sent" releases it. Retention never deletes a draft in that state.
- **Vault missing:** without `PII_VAULT_KEYS` the details cannot be sealed, so writing refuses with
  `masking_unavailable` rather than store a value in the clear.
- **Private mode:** the user's provider is used for retrieval and the agent, as for replies.
- **A typed `[PHONE_REDACTED]`-style marker or an unknown placeholder** blocks the send, as for replies.

## Implementation notes

- Agent (`backend/email_agent.py`): `generate_new_email`, `evaluate_new_email` and
  `rewrite_new_email`, sharing `assess`, `repair` and the review reasons through keyword arguments
  whose defaults keep the reply path unchanged. New fence tag `email_brief`.
- Backend: `app/compose.py` (service), `app/compose_routes.py` (router), `gmail_send.send_new`.
- `mask_typed_text` takes an optional `replace` callback; its default output is unchanged, so the
  listener's shared masking vectors still hold.

## Decisions

- 2026-10-21: saved drafts, not page-only (owner). Typed fixed-format details are restorable
  placeholders in a per-draft vault, so a phone number in a brief can be sent.
- 2026-10-21: an unknown send outcome is settled by the user, not a reconciler: a new email has no
  thread to look in, and matching on Message-ID depends on Gmail keeping ours, which is unverified.
  A claim reads as in flight for 10 minutes (past the slowest send); when Gmail's answer is lost the
  request is over, so the draft can be settled at once.
- 2026-10-21 (review): the model's answer is written only over the draft it was written from; an edit
  made meanwhile in another tab refuses it with `conflict` instead of being overwritten.
