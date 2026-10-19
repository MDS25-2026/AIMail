# Normalisation v2, stages 1 and 2: clean text, then language, an English copy and deadlines

- **Status:** built by veyroxie (2026-10-13); waiting to be pushed by a teammate
- **Owner:** veyroxie (spec and code); pusher or builder: a teammate while veyroxie's GitHub account is
  under review
- **Related:** `normalisation-v2.md` (the plan), `normalisation-v2-stage3.md`, `normalisation-v2-stage4.md`
- **Code:** finished on branch `feat/normalise-stage2`, handed over as `aimail-normalise.bundle`. Pushing
  it is the quick route (`HOW-TO-PUSH.txt`). This spec says what it does, task by task, so it can be
  reviewed, or rebuilt if the team prefers.
- **Estimate if rebuilt:** stage 1 about 2 h, stage 2 about a day

## Goal

AIMail's models and rules were built for English. Malay, Chinese and mixed mail did worse at every step,
and some steps could not work at all: no deadline was ever stored (0 of 238 emails). Stage 1 cleans the
text before masking. Stage 2 gives every email its language, an English copy when it is not in English,
and the earliest deadline it sets. Stages 3 and 4 then use them.

---

## Stage 1

### Task 1.1: clean text before masking (listener, 1 h)

**Why:** Chinese mail often writes digits and addresses in full-width characters (`０１２-３４５６７８９`,
`ａｌｉ＠ｍａｉｌ．ｃｏｍ`). The listener's regex floor only knows plain ones, so those phone numbers and
emails were not masked: a privacy gap. Zero-width characters also split a name apart, so the masker
missed it.

**Build** (`listener/cleantext.go`):
- `cleanText(text string) string`:
  - **Full-width to plain:** digits `０-９`, Latin letters `Ａ-Ｚ ａ-ｚ` and `＠ ． － ＋ ＿` become their
    plain forms. Subtract `0xFEE0` from the code point.
  - **Invisible characters removed:** U+200B, U+200C, U+200D, U+2060 and U+FEFF. Write U+FEFF in Go as
    `"\xef\xbb\xbf"`, because Go rejects the `﻿` escape.
  - **Left alone:** Chinese punctuation (`，：（）`) and everything else. **Do not use Unicode NFKC**, which
    also rewrites `m²` to `m2` and `½` to `1⁄2`, breaking the unit reader.
- Call it at the start of `maskText` in `listener/main.go`:
  `maskPII(cleanText(text), v)`. That covers the body, preview, subject, attachment text and sent
  mail in one place.

**Tests** (`listener/cleantext_test.go`):
- **Masked:** a full-width phone number, and a full-width email address.
- **Unchanged:** a Chinese sentence with `，`, `m²`, `½` and `（）`.
- **Joined:** a name with a zero-width space inside it comes back whole.

### Task 1.2: one quote splitter in the backend (1 h)

**Why:** the stages after this judge only what the sender wrote, not the earlier email quoted under it.
The backend had the splitter inside `app/waiting.py`. The listener (`sla.go`) and the dashboard
(`src/lib/quotedText.ts`) have their own copies, and the backend's lacked Outlook's `Sent:` line.

**Build:**
- **Move** `own_text` and its three patterns from `backend/app/waiting.py` to
  `backend/app/normalise/quotes.py`.
- **Add** `Sent:\s` to the quote-start pattern, so it matches the other two.
- **Update** `app/waiting.py` to import `own_text` from there, and `tests/test_waiting.py` to import it
  from the new module.

**Tests** (`backend/tests/test_normalise_quotes.py`), one case each:
- Outlook's From and Sent block;
- a `Sent:` line alone;
- the Malay header ("Pada ... menulis:");
- the Chinese header ("写道：");
- the two-line "On ..." / "wrote:" header;
- no quote at all.

---

## Stage 2

### Task 2.1: migration 0044 (15 min)

`backend/app/db/migrations/0044_normalised_copy.sql`:

```sql
ALTER TABLE messages ADD COLUMN IF NOT EXISTS language TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS subject_en TEXT;
ALTER TABLE messages ADD COLUMN IF NOT EXISTS own_text_en TEXT;
CREATE INDEX IF NOT EXISTS messages_language_pending_idx ON messages (created_at) WHERE language IS NULL;
```

- **The model:** add the three columns to `Message` in `backend/app/db/models.py`.
- **The schema doc:** record them in `specs/context/db-schema.md`.
- **Run it on the live database before the PR merges** (`make migrate` from a laptop with the shared
  `.env`). Render does not run migrations, and code that deploys first breaks every email query. The
  migration only adds columns, so running it early is safe.

### Task 2.2: the deadline reader (3 h)

**Why:** `deadline_at` exists, but nothing filled it, so the To-do could not show due dates and priority
could not use them.

**Build:**
- **Month names in `backend/app/normalise/dates.py`:**
  - add the Malay months whose first three letters differ from English to `MONTHS`: `mac` 3, `mei` 5,
    `ogo` 8, `okt` 10, `dis` 12;
  - add a Chinese date pattern `(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号號]` to `dates_in`.
- **New module** `backend/app/normalise/deadlines.py`, with
  `deadline_in(text, sent_at, zone) -> datetime | None`:
  - **Finds deadline wording:** `by`, `before`, `no later than`, `deadline`, `due`, `latest by`, `at the
    latest`, and Malay `sebelum`, `selewat-lewatnya`, `paling lewat`, `tarikh akhir`.
  - **Looks at up to 60 characters after each cue,** stopping at the end of the sentence.
  - **The day:**
    - an exact date (via `dates_in`);
    - `tomorrow`/`esok`;
    - `today`, `tonight`, `end of day`, `EOD`, `COB`, `hari ini`, or a time alone, all meaning today;
    - a weekday in English or Malay, meaning its next occurrence, today counting;
    - `end of week`, `this week`, `minggu ini`, meaning Friday;
    - `next week`, `minggu depan`, meaning the coming Monday.
  - **The time:** `noon`, `midday` or `tengah hari` (12:00); `6 pm`, `6:30pm` or `18:30`; otherwise 17:00.
  - **Resolved** in the owner's time zone, against when the email was sent.
  - **Kept:** only deadlines after the email was sent and at most 180 days ahead. "By 1 October" sent
    on 13 October would otherwise roll to next year.
  - **Returns** the earliest, in UTC.
  - **Named constants:** `DEFAULT_DEADLINE`, `NOON`, `CUE_WINDOW_CHARS`, `MAX_AHEAD`.

**Tests** (`backend/tests/test_deadlines.py`, sent on Tuesday 13 October 2026, 10:00 in Kuala Lumpur):
- **The vendor review email:** "by 12:00 noon tomorrow, Wednesday 14 October … by 6:00 pm on Thursday
  15 October" gives Wednesday 12:00, the earliest.
- **Each gives the right time:** "by Friday"; "before 5pm today"; "by end of week"; "due on 30 October
  2026"; "sebelum Khamis"; "selewat-lewatnya 20 Oktober"; "no later than 2026-10-21 18:30".
- **None:** a date with no cue; a past date with a cue; no date at all.
- **Dates read:** a Chinese date, and a Malay month.

### Task 2.3: the normalise job (4 h)

**Why:** every later step should read an English copy of a non-English email, made once and stored, not
translated again on every request.

**Build** (`backend/app/normalise/pipeline.py`), with `normalise_pending(limit) -> int`:
- **Picks** emails with `language IS NULL`, masking `complete` and a body, newest first, up to `limit`.
- **For each email:**
  - **The sender's own text:** `own_text(plain_text(body_masked))`.
  - **Its language:** `detect_language(subject + own text)` (`app/core/language.py`).
  - **An English copy, when it isn't English:**
    - **Which model:** `provider_for(owner)`. If that's the local model and this server has none
      (`is_offered()` is false), make no copy and make no call.
    - **Two agent calls:** `/translate` for the subject, then for the own text, through
      `agent_client.call` with a `TranslateRequest(text, language="en", provider)`. Cut the own text at
      the last paragraph that fits within `MAX_TRANSLATE_CHARS`.
    - **The privacy receipt:** save each call's egress with `save_egress(..., message_id=...)`.
    - **On refusal (HTTP 422, unfaithful or too large):** save the refusal egress, and make no copy.
      Every step then reads the original.
    - **On any other failure** (agent down, 5xx, malformed answer): stop the pass and leave the email
      queued for the next one. Do not mark it done.
  - **The deadline:** `deadline_in(english copy or own text, received_at or created_at, owner's time
    zone)`. The time zone comes from `quiet_hours.settings_for(owner).effective.timezone`, or the
    company default when there's no owner.
  - **Store** `language`, `subject_en`, `own_text_en` and `deadline_at`, in an update that only applies
    while `language IS NULL`, so two workers never overwrite each other. Keep an existing `deadline_at`
    when none is found.
- **Register it** in `backend/app/worker.py` as `Job("normalise", …)`, every 30 s, 20 emails per pass,
  as named constants. Add `"normalise"` to the job list in `tests/test_worker.py`.

**Tests:**
- **`backend/tests/test_normalise_pipeline.py`** (stubbed agent):
  - only the masked own text is sent;
  - a refusal leaves no copy;
  - an outage keeps the email queued;
  - Private mode without a model here makes no call;
  - long text is cut at a paragraph.
- **A database test** in `backend/tests/test_database.py`:
  - a Malay email gets `ms`, an English subject and own text, and a deadline of Friday 17:00 Kuala
    Lumpur time;
  - an English email gets `en` and no copy.

### Task 2.4: clean-up paths (30 min)

- **Retention** (`backend/app/retention.py`, `_message_content`): also clear `own_text_en` when the body
  is cleared. The English subject is cleared with the original subject (audit M2).
- **Reprocess** (`listener/reprocess.go`): also clear `language`, `subject_en` and `own_text_en`, so a
  re-read email is normalised again. Extend `TestReprocessClearsEverythingWrittenInTheOldNumbering`.
- **Privacy notice** (`docs/privacy/privacy-notice.md`, "What goes to Google Gemini"): a new bullet
  saying the masked subject and the sender's own text of non-English emails are translated into English
  once, shown in the privacy receipt, deleted with the email's text, and made by the local model in
  Private mode.

### Cut on purpose

- **What:** a money and number reader (`RM1.2k`, Chinese numerals), a Malay short-form dictionary, and
  link tracking stripping.
- **Why:** the English copy already reads short forms and numbers correctly, so none of them changes
  what the later steps see. They can come back if a measured case needs them.

## Definition of done

- [ ] `make check` passes with `.env` moved aside: 1064 backend tests, 287 dashboard tests and the
      listener's tests, as measured on the finished branch.
- [ ] The database tests pass on a fresh pgvector database: 37, including migrating twice with no change.
- [ ] Migration 0044 has been run on the live database before the PR merges.
- [ ] `specs/context/db-schema.md` and the privacy notice are updated.
- [ ] Reviewers named:
  - **JiaJun:** `listener/cleantext.go`;
  - **Hanif:** the translate calls;
  - **veyroxie:** owner, over WhatsApp.
