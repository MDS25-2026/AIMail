# Normalisation v2: clean, English-first, then everything else, then translation

- **Status:** stage 1 built (PR #234); stage 2 built 2026-10-13
- **Owner:** veyroxie
- **Related issue:** #224
- **Builds on:** `normalisation-layer.md` (numbers, units, dates), `multilingual-masking.md`
- **Last updated:** 2026-10-13

## Goal

Every model and rule in AIMail (category, priority, SLA and deadlines, summary, action items, RAG,
search, critic) was built on English and reads whatever language arrives. Malay, Chinese and mixed
mail does worse at every step, and some steps cannot work at all (no deadline is ever stored). Clean
the text once, keep an English copy of every non-English email (masked, never raw), and point every
step at it; translate only at the end, for the reader and for the reply.

## Pipeline

1. **Listener, before masking:** clean the text (stage 1).
2. **Listener:** mask (`multilingual-masking.md`), store the original, masked.
3. **Backend worker, masked text only:** tag the language, keep an English copy, read dates, deadlines,
   money and Malay short forms (stage 2).
4. **Everything else reads the English copy** (stage 3).
5. **Translation last:** replies in the sender's language; the reader's "Translate" uses the stored
   copy (stage 4).

## Stage 1: clean text (listener) and one quote splitter (backend)

- **Full-width ASCII to plain** before masking: digits, Latin letters and `@ . - + _` written full-width
  (common in Chinese mail: `０１２-３４５６７８９`, `ａｌｉ＠ｍａｉｌ．ｃｏｍ`) become plain, so the regex floor
  sees phones, IC numbers and emails it missed. Chinese punctuation (`，：（）`) is left as written, and
  NFKC is not used: it would also rewrite `m²` and `½`, which the unit reader needs.
- **Invisible characters removed:** zero-width space, joiner, non-joiner, word joiner and byte-order mark
  split names and numbers apart for the masker.
- **One quote splitter in the backend** (`app/normalise/quotes.py`), the same lines as `listener/sla.go`
  and the dashboard's `quotedText.ts`; `app/waiting.py` uses it, and stages 2 and 3 judge only the
  sender's own text.

## Stage 2: normalise (backend worker; schema change approved 2026-10-13)

- `messages.language` (en, ms, zh), `subject_en`, `own_text_en`: the English copy of a non-English
  email, translated from masked text by the request's model (Gemini, or Gemma in Private mode), refused
  when figures or placeholders change; on refusal every step reads the original.
- Dates and deadlines: Malay and Chinese dates and relative days resolved against the sender's Date
  header and the owner's time zone, filling `deadline_at`.
- Deadlines read from the English copy, or the original when there is none: a deadline word ("by",
  "before", "no later than", "due", Malay "sebelum", "paling lewat") then a date, weekday, "tomorrow",
  "end of day", "noon" or a time; a day with no time is due at 17:00; the earliest after the email was
  sent wins; one more than 180 days ahead is ignored (a past date rolled to next year).
- The English copy covers the sender's own text only (`app/normalise/quotes.py`), cut at a paragraph to
  the agent's limit. A refused translation leaves no copy; an agent outage leaves the email queued.
- **Cut from stage 2, on purpose:** a money and number reader for `RM1.2k` or Chinese numerals, a Malay
  short-form dictionary and link tracking stripping. The English copy already reads short forms and
  numbers correctly, so none of them changes what the later steps see; they can come back if a measured
  case needs them.

## Stage 3: everything else reads the English copy

Category (Gemini or Gemma, in the routing call), priority and SLA, summary and action items, RAG, search
(both versions indexed), critic; To-do due badges and a Notifications filter.

## Stage 4: translation last

Replies in the sender's language: Gemini writes directly in it; Gemma drafts in English and translates
(checked). "Translate" on an email reads the stored English copy. One reprocessing run then applies
masking, normalisation and the English copy to stored mail, with the owner's yes.

## Acceptance criteria (stage 1)

- [ ] Given `call ０１２-３４５６７８９` or `ａｌｉ＠ｍａｉｌ．ｃｏｍ`, then the phone or email is masked.
- [ ] Given a name with a zero-width space inside it, then it is masked as one name.
- [ ] Given Chinese text, then its punctuation is unchanged; given `5 m²`, then it is unchanged.
- [ ] Given a reply with a quoted email, then the backend's splitter returns only the new text, as the
      listener's and the dashboard's do.
