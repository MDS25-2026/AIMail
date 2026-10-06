# Translation: the dashboard in three languages, and a checked translation of any email

- **Status:** shipped
- **Owner:** veyroxie (Lane D code, pending Han's review)
- **Related issue:** hackathon-reuse review (translate.py, i18n.js), user request 2026-09-29
- **Last updated:** 2026-09-29

## Goal

A reader works in English, Bahasa Melayu or Simplified Chinese, and can read any email in their
language without the translation becoming a way for personal data or false figures to appear.

## Scope

**In scope**
- **Interface (i18n).** Every dashboard string comes from `src/locales/{en,ms,zh}.ts` through
  `react-i18next` (MIT). The Malay and Chinese files are typed against the English one, so a
  missing key is a compile error, and `t()` keys are type-checked. Language, theme and unit system
  live in cookies, so the server renders the chosen language and theme on the first paint.
- **Email translation.** `POST /emails/{id}/translate` sends the *masked* body (markup stripped)
  to the agent's `/translate`, which asks Gemini for a faithful translation and then checks it:
  1. the redaction markers are exactly the same multiset (a lost marker may have been guessed);
  2. every figure in the source is in the translation, compared as values through the
     normalisation layer ("1,250.00" and "1.250,00" agree).
  A translation failing either check is refused with 422 and never shown.

**Out of scope**
- Translating drafts or sending in another language: the draft already follows the thread.
- Reversible masking (restoring names after translation): it would mean storing the mapping from
  token to real value, which the masking design rules out.

## Acceptance criteria

- [x] A translation that fills in `[Redacted]` or changes RM 1,250.00 is refused
      (`tests/test_email_agent_gates.py`); a Chinese date reordering keeps every figure.
- [x] Live against Gemini, a synthetic masked email translated to ms, zh and en passes both checks.
- [x] With cookies `aimail-theme=dark; aimail-lang=zh`, the server renders `<html lang="zh" class="dark">`;
      unrecognised cookie values fall back to the defaults.
- [x] `tsc --noEmit` fails if ms.ts or zh.ts lacks a key en.ts has.

## Security & privacy notes

Only masked text reaches the model, which is what drafting already sends: no new exposure. The
translation is not stored. Cookies hold display preferences only.

## Open questions

- The Malay and Chinese strings were written without a native reviewer. They need one before a
  real user sees them.
