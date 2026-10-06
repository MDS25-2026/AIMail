# Holding reply: the user's own words, sent only when they would want it sent

- **Status:** built 2026-10-06 (owner: "1 then", the meeting 30 task "quiet hours, auto-reply
  templates"); checked live 2026-10-06: a real email after hours was scheduled, re-checked at
  the end of the hold window and sent 7 s later, Gmail confirmed, every step audited
- **Owner:** veyroxie (touches Lane A, Lane B and Lane D; each lane owner reviews their part)
- **Related issue:** product brainstorm 2026-09-30 ("safe" and "understood" for a work inbox)
- **Last updated:** 2026-10-06

## Goal

When the user cannot reply for a while (after hours, on leave), a sender who needs an answer
hears back promptly, in words the user wrote, and never in a way that leaks data, answers a
phisher or starts a loop with another auto-responder.

## User story

As an employee using AImail on my work inbox, I want to set a holding reply once, with my own
text and my own conditions, so that people waiting on me know when to expect an answer without
me checking email at night or on leave.

## Why this is not Gmail's vacation responder

Gmail already sends a fixed message between two dates, once per sender every four days. This
feature earns its place only through conditions Gmail cannot evaluate: whether the email needs a
reply at all, whether it looks like phishing, whether the sender is someone the user actually
corresponds with, and which language the sender wrote in. If those are cut, cut the feature.

## Scope

**In scope**
- Per-user settings: when it is active, who may receive it, which emails qualify, the cooldown,
  and one template per language (en, ms, zh).
- Template placeholders filled locally: `{return_date}` from the leave dates, `{name}` from the
  From header's display name with a plain fallback greeting when there is none.
- A hold window: a holding reply is scheduled, not sent, and is cancelled if the user replies first.
- Always-on safety rails that the user cannot switch off (below).
- An audit row for every scheduled, sent and cancelled holding reply.

**Out of scope**
- Any AI-written text in the reply. The model never writes or edits a holding reply.
- Organisation-wide policy set by an admin (the admin console is read-only; see ADR 0004's
  "Revisit when").
- Shared inboxes (support@, sales@): this is for a person's work inbox.
- Quiet hours for the user's own outgoing mail: a separate feature, sharing the working-hours setting.

## Conditions

**Always on (not configurable):**
1. The message's `masking_status` is `complete`. A quarantined row has no content to judge.
2. The phishing signal does not fire on the masked body.
3. `reply_to` is empty or has the same address as `from_addr`.
4. The message is not automated: no `List-Id`, no `Precedence: bulk|list|junk`, no
   `Auto-Submitted` other than `no`, no empty Return-Path, and the sender is not a
   noreply / mailer-daemon / postmaster address (RFC 3834 section 2).
5. The sender has not received a holding reply within the cooldown.
6. The daily cap (`HOLDING_REPLY_DAILY_CAP`) has not been reached.
7. The user has not replied in the thread by the end of the hold window.

**User-chosen:**
- **When:** outside working hours / during leave dates / always.
- **Who:** people the user has corresponded with (default) / the user's own domain / everyone.
- **Which emails:** only those AImail judges to need a reply (default) / all.
- **Cooldown per sender:** 4 days by default, matching Gmail so the behaviour is familiar.

Every condition fails closed: a signal that cannot be computed means no holding reply.

## Acceptance criteria

- [ ] Given the feature is not enabled, when any email arrives, then no holding reply is scheduled
      (the feature is opt-in).
- [ ] Given it is enabled and every condition holds, when an email arrives, then a holding reply
      is scheduled for `received_at + HOLD_WINDOW` and sent at that time, with headers
      `Auto-Submitted: auto-replied`, `In-Reply-To` and `References`, into the same Gmail thread.
- [ ] Given a scheduled holding reply, when the user replies in that thread before it is due,
      then it is cancelled and the audit row records why.
- [ ] Given an email carrying `List-Id`, `Precedence: bulk` or `Auto-Submitted: auto-replied`,
      then no holding reply is scheduled.
- [ ] Given an email whose masked body trips the phishing signal, or whose Reply-To differs from
      From, then no holding reply is scheduled.
- [ ] Given a sender who received a holding reply 3 days ago with a 4-day cooldown, when they
      email again, then no holding reply is scheduled.
- [ ] Given an email written in Chinese and a `zh` template, then the `zh` template is sent;
      given no template for the detected language, then the user's default-language template is sent.
- [ ] Given `{return_date}` in the template and leave ending 2026-10-15, then the sent text
      contains that date formatted for the template's language; given no leave dates set, the
      settings form refuses to save a template using `{return_date}`.
- [ ] Given a From header with no display name, then `{name}` renders the template language's
      plain greeting fallback, never an empty string or the email address.
- [ ] No request to Gemini or the agent is made to produce, edit or translate the holding reply
      (asserted by a test that fails on any agent call in the send path).

## API surface

To be added to `specs/context/api-contracts.md` before implementation:

- `GET /settings/holding-reply`: the user's settings, or the defaults with `enabled: false`.
- `PUT /settings/holding-reply`: validates and saves. Rejects unknown placeholders and
  `{return_date}` without leave dates.
- `GET /holding-replies?limit=`: recent scheduled, sent and cancelled holding replies, for the
  user to see what went out in their name.
- `DELETE /holding-replies/{id}`: cancels one that is still inside its hold window.

## Data model

To be added to `specs/context/db-schema.md` with the migration:

- **`holding_reply_settings`** (one row per user, FK `user_profile.id`): `enabled`, `active_when`
  (`outside_hours|leave|always`), `work_days`, `work_start`, `work_end`, `timezone`,
  `leave_from`, `leave_until`, `audience` (`correspondents|domain|everyone`), `scope`
  (`needs_reply|all`), `cooldown_days` (default 4), `templates` (JSONB, keyed by language).
  Enums enforced by CHECK constraints.
- **`holding_reply`** (one row per scheduled reply): `message_id` FK, `recipient_addr`,
  `language`, `scheduled_for`, `sent_at`, `cancelled_reason`, `sent_message_id`. Indexed on
  `(user_id, recipient_addr, sent_at)` for the cooldown check. Unique on `message_id`, so a
  message can never receive two holding replies.
- **`messages.is_automated`** (`BOOLEAN NOT NULL DEFAULT false`, Lane A): set by the listener from
  the headers in condition 4. Existing rows stay `false`, which is safe only because the feature
  never looks at messages received before it was enabled.

## Dependencies

- Lane A: the listener reads the automation headers it currently ignores.
- Lane B: the scheduler, settings routes and send path (`send_reply` needs extra headers).
- Lane D: a settings card and a "sent in your name" list.
- No new third-party dependency. Language detection is a small local heuristic (CJK code points
  mean zh; a Malay stop-word ratio means ms; otherwise en), not a library.

## Edge cases & failure modes

- **Backend down when a reply falls due:** the scheduler sends late replies on restart only if
  still within `HOLD_WINDOW * 3` of their due time; older ones are cancelled as `stale`. A holding
  reply that arrives a day late is worse than none.
- **Two backend instances:** the send claims the row atomically (`UPDATE ... WHERE sent_at IS NULL
  AND cancelled_reason IS NULL`), the same claim-then-act shape as `approve_and_send`.
- **Loop with another responder:** blocked by condition 4, by the cooldown, and by our own
  `Auto-Submitted` header, which a compliant responder honours.
- **User replies from Gmail rather than AImail:** the listener must see sent mail in the thread,
  or condition 7 only catches replies sent through AImail. See open questions.
- **Settings changed while replies are scheduled:** each reply re-checks every condition against
  the current settings at send time.

## Security & privacy notes

- The template is user-authored and stored in Postgres. It never reaches a model.
- `{name}` comes from `from_addr`, which is stored unmasked and is documented as never entering a
  model payload. The substitution is local string formatting, so that rule still holds.
- The reply never quotes or refers to the incoming email's content, so nothing masked is ever
  unmasked into it.
- An auto-reply confirms the address is live. The default audience (`correspondents`) and the
  phishing and automation rails exist to limit that to people the user already deals with.
- The rows in `holding_reply` are personal data (recipient addresses). Retention follows
  `messages`.

## Decisions (2026-10-06)

The open questions below were settled with their recommendations when the owner chose to build:

- **"Needs a reply"** is the agent router's verdict, which drafting already produces: an email it
  routed as needing no reply has no draft. A holding reply under scope `needs_reply` waits for the
  draft; if drafting has not finished by the stale limit, nothing is sent (fails closed).
- **A reply the user sent from Gmail** is found at send time with one `threads.get` on the user's
  own token: any message labelled SENT after the incoming one cancels the holding reply.
- **Correspondents** are found at send time with one Gmail search (`to:<address> in:sent`, one
  result) on the user's token. Any error counts as "not a correspondent" (fails closed).
- **The phishing check** moves to `app/core/phishing.py`, imported by both the agent and the backend.
- **Quiet hours** (meeting 30's wording) are the hours this reply is active: outside the user's
  working hours, or during leave. The working-hours model lives in this feature's settings.
- **Scheduling** happens when the listener has stored a message: the backend's poller schedules
  qualifying emails, re-checks every condition when the hold window ends, and sends or cancels.
- **Language** is detected locally (Chinese characters mean zh; Malay common words outnumbering
  English ones mean ms; otherwise en), matching the dashboard's Translate check.
- **`{name}` fallback** greetings: en "there", ms "tuan/puan", zh "您".
- Settings are only looked at for emails received after the feature was last switched on
  (`enabled_at`), so switching it on never answers a backlog.

## Open questions (as first written)

- **What decides "needs a reply"?** The priority classifier scores importance, not whether a
  reply is expected. Options: the agent router's category (costs a Gemini call on masked text), or
  a local rule (question mark or request verb addressed to the user). Recommendation: start with
  the router, since drafting calls it already, and fail closed when it is unavailable.
- **Does the listener see the user's sent mail?** If it ingests INBOX only, detect a user reply
  with a Gmail API `threads.get` at send time instead. That is one call per due reply, so it is cheap.
- **Who counts as a correspondent?** AImail only knows replies it sent itself. A Gmail search for
  `to:<addr> in:sent` at scheduling time is accurate. It is one call per candidate, cached for
  the cooldown.
- **Where does the phishing check live?** `phishing_signal` is in `backend/email_agent.py` (Lane C).
  Either move it to a module both lanes import, or store its result on the row at generation.

## Out-of-scope future extensions

- The admin sets an organisation default, and the user overrides it.
- A per-sender allow and block list for holding replies.
- Suggesting a holding reply when the user marks leave in Google Calendar.

## Implementation notes

- `HOLD_WINDOW` (10 minutes), `HOLDING_REPLY_DAILY_CAP` (50) and the poll interval go in
  `app/core/constants.py`, not in `.env`: they are product behaviour, not deployment config.
- The scheduler can share the pre-generation poller's lifespan loop in `app/main.py`.
- Share the working-hours model with the quiet-hours feature when it is specified.

## Protected decisions

<!-- BEGIN PROTECTED -->
A holding reply contains only text the user wrote; no model writes, edits or translates it. The
feature is opt-in, and the always-on conditions cannot be disabled by any setting.
Rationale: a company is liable for what an automated agent says in its name (Moffatt v. Air
Canada, 2024), and an automatic reply to a phisher or a mailing list is a privacy failure.
DO NOT change this without the mailbox owner's approval recorded in docs/decisions/shared.md.
<!-- END PROTECTED -->
