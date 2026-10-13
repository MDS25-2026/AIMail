# Write in my language, send in theirs

- **Status:** built 2026-10-13
- **Owner:** veyroxie
- **Related issue:** #224 (item T)
- **Last updated:** 2026-10-13

## Goal

Someone whose working language is Malay or Chinese often has to answer English email. AIMail drafts in
the email's language, but writing or rewriting a reply is easier in your own. Let them write it in
their language and send it in the email's, after checking the translation.

## Scope

**In scope**

- **"Translate my reply to {language}"** by the draft, shown only when the draft is not in the email's
  language (the dashboard's language heuristic, `mainLanguage` and `needsTranslation`), the draft is not
  empty, and it can still be edited.
- **The translation replaces the draft;** "Your words" shows what you wrote, with "Back to my words".
  The translated draft then goes through every check any draft does before it can be sent (unfilled
  placeholders, tone, send permission, the undo window).
- **Masked, as Refine is:** known details become their placeholders, new fixed-format details (phone
  numbers, emails, IC numbers) are masked, and typed names are hidden and put back after. The model
  never sees the real details.
- **Faithful or refused:** the agent's existing check refuses a translation that changes or drops a
  figure or a placeholder (`translation_unfaithful`); the draft is left as it was and the reader is told.
- **The Refine box's hint** says instructions work in any language (they already did).

**Out of scope**

- Storing the reader's own-language version, or translating the email's later replies automatically.

## Acceptance criteria

- [ ] Given an English email and a draft written in Malay, then "Translate my reply to English" is
      offered; given a draft already in English, it is not.
- [ ] Given the reader translates, then the draft becomes the English text, "Your words" shows the
      Malay, and "Back to my words" restores it.
- [ ] Given the reply names a person and a phone number, then the text sent to the model holds their
      placeholders, never the name or the number.
- [ ] Given the agent finds the translation unfaithful, then the draft is unchanged and the reader sees
      why.

## API surface

- `POST /emails/{id}/translate-draft` `{text}` (rate-limited like other model calls) returns
  `{language, text}`: the email's language and the reply in it, in placeholder form. 422
  `translation_unfaithful` or `too_large`; 409 `private_model_unavailable` as for any model call.
  Audited as `translate_email` with `draft: true`.

## Data model

None. Nothing is stored.
