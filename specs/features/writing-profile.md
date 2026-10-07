# Writing style: drafts that sound like the user, on their terms

- **Status:** accepted 2026-10-06 (owner: "okay all sounds good. i thk off by default, but shld
  also be able to mask ah"); building
- **Owner:** veyroxie (backend storage and learning, agent prompt, Settings card)
- **Related issue:** product brainstorm 2026-09-30 ("understood"); feeds
  [`model-feedback-routing.md`](./model-feedback-routing.md)
- **Last updated:** 2026-10-06

## Goal

Drafts open, close and phrase things the way the user does, so they need fewer edits. The user
decides how AImail learns their style, sees exactly what the AI is given, and can delete any of it.
No model is trained: the style is plain text added to the drafting prompt.

## User story

As an employee, I want to tell AImail how I write, show it a few replies that sound like me, and
optionally let it notice my habits, so that its drafts sound like me without me feeling watched.

## Scope

One "Your writing style" card in Settings with three independent parts. Any mix can be used.

**In scope**
- **Describe it:** one free-text line ("Warm but brief, no jargon"), with quick picks (More
  formal, Always say thank you, Shorter, Warmer) that add or remove a phrase in one tap.
- **Example replies:** up to `MAX_EXAMPLES` (3) replies that sound like the user, pasted in or
  added with "Use as an example" on a reply they sent.
- **Learn from what I send:** a switch, **off by default**. While on, each send records the draft
  as shown and what was sent, and a rule-based learner lists habits (greeting, sign-off phrase,
  typical length, repeated word swaps) with their evidence.
- **Reuse my past replies (added 2026-10-07):** while learning is on, each send also stores the
  email and the reply as one searchable item, so a later draft for a similar email can see how the
  user answered before. It is found by the same search as documents (Gemini vectors normally,
  local ones in Private mode) and shown in the draft's sources as "Your earlier reply". Only sends
  made while the switch is on are stored. It never appears in the document library.
- **Masked before storage:** every description, example and learned habit is masked before it is
  stored, and only the masked text is kept. The card shows exactly that text ("What the AI sees").

**Out of scope**
- Fine-tuning or training any model on the user's email.
- Learning across users, or a team voice for shared inboxes.
- Any admin view of a style.

## Acceptance criteria

- [ ] Given a description or a pasted example, when it is saved, then names, email addresses, phone
      numbers, IC and card numbers are replaced with `(hidden)` before storage, and the response
      returns the stored text. If the masker is unreachable, nothing is stored (503).
- [ ] Given "Use as an example" on a sent reply, then the stored example is that reply's sent text,
      with its placeholders and any remaining detail masked the same way.
- [ ] Given `MAX_EXAMPLES` examples, when another is added, then it is refused (409).
- [ ] Given learning is off (the default), when the user sends, then no draft/sent pair is stored.
- [ ] Given learning is on, when the user sends, then the draft as shown, the sent text (both in
      placeholder form) and the edit ratio are stored on the message.
- [ ] Given a habit observed in fewer than `MIN_EVIDENCE` (3) sends, then it is not listed. One
      reply to one colleague does not become a habit.
- [ ] Given a candidate habit containing a digit, `@`, a URL, a placeholder or masking mark, or a
      capitalised word not at sentence start, then it is dropped and never stored.
- [ ] Given a pair whose edit ratio is above `REWRITE_RATIO` (0.8), then it feeds only length, not
      word swaps: a rewrite says the draft missed, not how the user phrases things.
- [ ] Given a learned habit, then the card shows it with its evidence ("in 7 of your last 10
      replies") and a delete control; a deleted habit never returns.
- [ ] Given learning is on, when the user sends, then the email and the reply are stored as one
      search item of at most `PAST_REPLY_MAX_CHARS` (4000), masked with `mask_for_style`, so every
      placeholder is `(hidden)`: a copied placeholder can never be filled from another thread's
      details. A failure here (masker or database down) is logged and never fails the send.
- [ ] Given a stored past reply, then it is labelled "Your earlier reply" (never the subject, which
      is not masked) and is left out of the document library.
- [ ] Given "Delete everything", then the description, examples, habits, every stored pair and
      every stored past reply are removed, and learning is switched off. Deleting the account removes them too.
- [ ] No admin route returns style data (asserted by a test over the admin app's route table).
- [ ] Given a style, then the draft and refine requests carry at most `STYLE_HINT_CHARS` (1200) of
      hint and at most `MAX_EXAMPLES` examples of at most `MAX_EXAMPLE_CHARS` (1500) each, fenced as
      data. The critic sees the same hint, so it does not mark a style-following draft off-tone.

## Precedence

- The sign-off **name** stays the owner placeholder chosen by the backend. A description or habit
  may set the closing phrase ("Thanks," / "Best regards,"), never the name.
- The tone picker (professional / casual) still applies; the style hint refines it.
- Examples are style only. The prompt tells the model never to copy their names, facts or figures,
  and they are not a grounding source.
- Past replies are context, like a document: the draft may reuse how an earlier email was
  answered. Each item opens with a line saying it answered a different email and that its dates,
  figures and promises do not carry over. The critic's grounding check treats it like any other
  retrieved source, so it does not catch an old date copied across; the user's review does.

## API surface

See [`../context/api-contracts.md`](../context/api-contracts.md#writing-style).

- `GET /profile/writing`: description, examples, habits with evidence, and the learning switch.
- `PUT /profile/writing/description`: `{description}`; returns the masked text that was stored.
- `PUT /profile/writing/learning`: `{enabled}`.
- `POST /profile/writing/examples`: `{text}` or `{emailId}` (a sent reply).
- `DELETE /profile/writing/examples/{id}`.
- `DELETE /profile/writing/habits/{id}`: hide a habit permanently.
- `DELETE /profile/writing`: delete everything.

The agent's `/process-email` and `/refine` gain `style_hint` (string) and `style_examples` (list).

## Data model

- `writing_style` (one row per user): `user_id` PK, `description` (masked), `learning_enabled`
  (default false), `updated_at`.
- `style_example`: `id`, `user_id`, `text` (masked), `source` (`pasted|sent`), `created_at`.
- `style_habit`: `id`, `user_id`, `kind` (`greeting|signoff|length|swap`), `value`, `evidence`,
  `out_of`, `suppressed`, `updated_at`; unique on (`user_id`, `kind`, `value`).
- Past replies: a `document` row with `doc_type = 'sent_reply'` and `source = sent://<message id>`,
  one chunk, embedded like any other chunk.
- `messages.draft_shown` (`TEXT NULL`) and `messages.edit_ratio` (`REAL NULL`), written only while
  learning is on.

## Dependencies

- `approve_and_send` in `backend/app/dashboard.py` (the capture point).
- `app/rag/mask.py` (`mask_document`, Presidio plus the typed-text floor) for masking.
- No new third-party dependency: the learner and edit ratio are standard-library code.

## Edge cases & failure modes

- **Sent unedited:** still recorded (ratio 0). An accepted draft is evidence too.
- **Masker down:** the save is refused with a clear message; nothing raw is stored.
- **Habits change:** the learner looks at the last `LEARN_WINDOW` (20) recorded sends only.
- **A learning failure never fails a send:** it is logged and the send result stands.

## Security & privacy notes

- **`(hidden)` and `(name)` can never be sent:** they count as redaction marks
  (`app/core/redaction.py`), so a draft that copied one is flagged by the critic's PII scan, warned
  about in the dashboard, and refused at send. The greeting habit is phrased without the mark.
- **Only masked text is stored** for descriptions and examples. Learned habits come from placeholder
  text and pass the screen above, so a name can only reach a habit by slipping past both.
- **Employer visibility:** the style is the employee's data about how they write. The admin console
  never reads it. Under the PDPA the employee can see, correct and erase it on the card.
- **Delete everything means everything:** description, examples, habits, suppressed markers and pairs.

## Open questions

- Presidio is called with `language: "en"`, so a name in a Malay or Chinese example may not be
  detected. A short capitalised line under a closing phrase is always hidden as a signature,
  since Presidio missed an unusual first name there in the live check. The card shows the masked text so the user can see and fix it; a multilingual model
  would close the gap.

## Out-of-scope future extensions

- A local fine-tuned model for style. Only worth trying if the edit ratio does not fall.
- Suggesting holding-reply templates in the user's own voice.

## Protected decisions

<!-- BEGIN PROTECTED -->
The writing profile is visible only to the user it describes. No admin route, report or export
reads it. Rationale: "understood" turns into "monitored" the moment an employer can read how an
employee writes. DO NOT change this without the mailbox owner's approval recorded in
docs/decisions/shared.md.
<!-- END PROTECTED -->
