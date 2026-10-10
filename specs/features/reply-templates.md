# Saved reply templates

- **Status:** built 2026-10-11 (pending review)
- **Owner:** veyroxie
- **Related issue:** #156 (epic #138, line 122); builds on `restorable-masking.md`
- **Last updated:** 2026-10-11

## Goal

Let people save the replies they write again and again (invoice details, meeting times, service
FAQs), and use one in a click, either word for word or adapted to the email by the AI, without
retyping the sender's name or anything the email already says.

## User story

As someone who answers the same billing question every week, I want my "Invoice details" reply
suggested when a billing email arrives, with the customer's name and invoice number already in,
so that I only check it and press Send.

## Scope

**In scope**
- **Templates in Settings:** title, text, language (EN, MS or ZH), and optional trigger keywords.
  Personal only.
- **Variables** written as `{{...}}` in the text, filled in this order:
  1. `{{name}}`: the sender's display name (`messages.from_addr`) as a placeholder, added to the
     thread map after the owner (`ThreadMap.add_sender`). The user sees the real name, the AI sees
     the placeholder, and the send restores it. Malay and Chinese words work too: `{{nama}}`,
     `{{名字}}`; likewise `{{nama saya}}`/`{{我的名字}}` and `{{hari ini}}`/`{{今天}}`.
  2. `{{my name}}` and `{{today}}`: the owner's name placeholder and today's date.
  3. With *Draft from template*, the AI fills variables from the email itself (an invoice number
     or an amount; these are not masked).
  4. Anything left is a highlighted blank for the user.
- **Two ways to use one** from the draft card:
  - *Insert*: the filled template (steps 1 and 2) replaces the text in the editor, like typed edits.
    Nothing is stored and no model is asked, so the stored AI draft and its review stay, and the
    Changes view compares the two. Over typed edits it asks first.
  - *Draft from template*: the agent adapts the template to this email, keeping the user's wording,
    filled by steps 1 to 3. It goes through the normal critic and checks.
- **Suggestion:** when an email's text contains a template's trigger keyword and matches its
  language, the draft card offers "Use your 'Invoice details' template?".
- **Translate this template:** creates a copy in another language with the existing translation
  feature, for the user to review.
- **The send check:** a leftover `{{...}}` refuses the send with `unresolved_placeholders`, like a
  placeholder with no value today. The dashboard names the blanks and disables Send first.
- Available on the dashboard's draft card and in the extension's side panel.

**Out of scope**
- Company-wide templates from the admin console (future step).
- Suggesting by category (#141) until the classifier is trusted; keywords first.
- Rich text or attachments in templates.

## Acceptance criteria

- [x] Given a template "Hi {{name}}" and an email whose sender's name was masked as `[PERSON_1]`,
      when the user inserts it, then the draft holds `[PERSON_1]`, the dashboard shows the real
      name, and the sent reply carries the real name.
- [x] Given `{{my name}}` and `{{today}}`, when inserted, then they are filled with no user input.
- [ ] Given *Draft from template* on an email stating "INV-2231 for RM 1,250", then
      `{{invoice number}}` and `{{amount}}` come back filled with those values (model behaviour;
      check by hand).
- [x] Given a draft still holding `{{meeting link}}`, when the user presses Send, then the send is
      refused with `unresolved_placeholders` and nothing reaches Gmail.
- [x] Given a sender with no display name, when `{{name}}` cannot be filled, then it stays a blank
      and the send check covers it. (It comes from `from_addr`, so the vault expiring does not empty it.)
- [x] Given a template with trigger "invoice" in English, when an English email mentions
      "invoice", then the suggestion shows; for a Malay email it does not.
- [x] Given *Draft from template*, then no request to the agent contains a vault value.
- [x] Given erasure, then the user's templates are deleted.

## API surface

- `GET/POST /templates`, `PUT/DELETE /templates/{id}`.
- `POST /templates/{id}/fill` `{emailId}` -> `{text}`: the filled template for the editor (Insert).
- `POST /templates/{id}/adapt` `{emailId, tone}` -> the email with the agent's rewrite stored.
- `POST /templates/{id}/translate` `{language}` -> a new template, unsaved until confirmed.
- The email payload gains `suggestedTemplateId` (null when none matches).

Changes go into `specs/context/api-contracts.md` in the same PR.

## Data model

- `reply_template` (migration 0038): `id`, `user_id`, `title`, `body`, `language`,
  `trigger_keywords text[]`, `last_used_at`, `created_at`, `updated_at`; RLS on; at most 50 per user. Written by the user, so it holds whatever the user types; it is
  never sent to the agent with vault values in it (the agent gets the template text and the masked
  email).

Changes go into `specs/context/db-schema.md` in the same PR.

## Dependencies

- `restorable-masking.md`: the thread map (`app/core/vault.py`) for the sender's and owner's
  placeholders, and `restore` at send.
- `translation.md` for *Translate this template*.
- The agent for *adapt* (an instruction plus the template, like refine).

## Edge cases & failure modes

- **Sender's name not found** (no display name, or a degraded masking row): `{{name}}` stays a
  blank.
- **Template typed with a real name in it** ("Hi Aisyah"): the user wrote it, so it is the user's
  own text; before *adapt*, the text is re-tokenised (`tokenise_known`) so known details become
  placeholders before reaching the agent.
- **Variable spelt differently** (`{{ Name }}`): matched case- and space-insensitively.
- **Two templates match:** the most recently used is suggested.

## Security & privacy notes

- Templates are personal and stored as typed; they are covered by erasure.
- The AI never receives vault values: *adapt* sends the masked email and the re-tokenised template.
- The send check keeps any unfilled `{{...}}` or placeholder from reaching a customer.

## Decisions

- 2026-10-10: Variables are filled from restorable masking, then automatically, then by the AI from
  the email, and only the rest by the user. Rationale: the user fills only what the email does not
  say.
- 2026-10-10: Both *Insert* and *Draft from template*.
- 2026-10-10: One language per template, with *Translate this template*.
- 2026-10-10: Personal templates only for now; company templates later.
- 2026-10-10: A leftover `{{...}}` refuses the send.
- 2026-10-11: *Insert* stores nothing; it fills the editor like typed edits. Rationale: a stored
  template draft would need a critic score it never had (the badge read "Review 0%"), and keeping
  the AI draft lets the Changes view (#149) compare the two. Alternatives: store it unreviewed.
- 2026-10-11: The sender's placeholder comes from `from_addr`. Since the follow-up fix it is the
  fixed `[PERSON_901]` (and the owner `[PERSON_900]`), so a newer message in the thread can no longer
  shift either (`restorable-masking.md`, step 12).
- 2026-10-11: A `{{...}}` blocks every send, not only template drafts, with no override. Rationale:
  the owner asked that no placeholder ever reach a recipient; a reply that genuinely needs double
  braces (code) has to be rephrased.
- 2026-10-11: Translating a template sends the masked typed text (fixed formats masked) with each
  variable as a `[VAR_n]` marker, and refuses a translation that lost one.
- 2026-10-11: AI filling of `{{invoice number}}` and the like depends on the model; it is not
  covered by an offline test and is the one criterion left to check by hand.
