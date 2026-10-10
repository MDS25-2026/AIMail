# Scanned attachments: read locally, or checked for signatures, faces and stamps first

- **Status:** built 2026-10-10 (pending review)
- **Owner:** veyroxie (Lane A code; JiaJun to review)
- **Related issue:** epic #138 line 19; extends `attachment-reading.md`
- **Last updated:** 2026-10-10

## Goal

Stop handwritten signatures, faces and ink stamps on scans from reaching Gemini. The attachment
reader redacts text it can read, but a signature is not text, so a signed letter or invoice that
passed the reader's gates used to go to Gemini with the signature intact.

## User story

As someone whose signed documents arrive by email, I want to choose whether scans stay on my
company's machine entirely, or are checked first and read by Gemini when clear, knowing what each
choice risks.

## Scope

**In scope**
- **The reader returns each scanned page's text** (as its local OCR read it, only for pages it
  read confidently and that are not identity documents) beside the redacted image. The listener
  masks that text with the rest of the email.
- **A per-user setting, `user_preferences.scan_reading`** (migration 0036), in Settings >
  Scanned attachments:
  - `local` (default): no scan image reaches Gemini. Each page's local text stands in for it.
  - `checked`: before each redacted image goes to Gemini, the listener asks a local vision model
    (`LOCAL_VISION_MODEL` on Ollama) whether it shows a signature, a face or a stamp. Only three
    clear noes send it; anything else keeps it here and uses its local text.
- `checked` is offered only where `LOCAL_VISION_MODEL` is set; going back to `local` always works.
- Private mode keeps every scan local, as before.
- If Gemini fails on a sent image, its local text is used.
- A synthetic test set (`listener/testdata/marks`, `generate.py`): 8 clear pages, 12 with a
  signature, initials, a stamp or a photo.

**Out of scope**
- Boxing out just the signature and sending the rest.
- Images embedded in email bodies (never sent to a model).
- Text PDFs, .docx and .xlsx: they return text, never images.

## Measured (2026-10-10, synthetic scans, three-question prompt)

| Model | Marked pages missed | Clear pages held back | Per page |
|---|---|---|---|
| `gemma4:e2b` (one question) | 10 of 12 | 0 of 8 | about 1 s warm |
| `gemma4:e2b` (three questions) | 5 of 12 | 0 of 8 | |
| Gemma-SEA-LION-v4 4B VL (Q4_K_M) | 1 of 12 | 2 of 8 | about 6 s |
| same, on 16 fresh pages it had not seen | 1 of 8 | 3 of 8 | |

So `checked` misses about 1 in 10 marks even on clean synthetic pages, and real scans will do
worse. That is why it is opt-in, and why the settings card says so. A cold start (model unloaded)
took 44.5 s; the listener's call times out at 60 s.

## Acceptance criteria

- [x] Given a scanned page read confidently, then the reader returns its text beside the redacted
      image; given an identity document, neither.
- [x] Given an owner with `local` (or no choice saved), then no scan image is sent to Gemini and the
      attachment's text includes each page's local text.
- [x] Given `checked` and a local model answering "stamp: true" for one of three images, then two
      are sent and the third is represented by its local text, and the withheld one is audited.
- [x] Given `checked` and no `LOCAL_VISION_MODEL`, or an unreachable model, or an answer that is not
      three clear noes, then no image is sent; after one failed call the rest are not asked.
- [x] Given `PUT /settings/scan-reading {mode: "checked"}` where no vision model is set up, then
      `409 scan_check_unavailable`; `local` is always accepted.
- [x] Given the synthetic set and the measured model, then the live test misses no more than 1 of 12
      marked pages (`marks_live_test.go`; `checked` accepts a measured miss rate by the owner's
      decision, see Decisions).

## API surface

- Reader `POST /read`: each item in `images` gains `text`. Pages withheld for a leftover
  identifier add their text to the top-level `text`.
- `GET /settings/scan-reading` -> `{available, mode}`; `PUT` `{mode}` (see
  `specs/context/api-contracts.md`).
- The listener calls Ollama's `POST /api/generate` with `model`, `prompt`, `images`,
  `format: "json"`, `think: false`, `temperature: 0`, and expects
  `{"signature": bool, "face": bool, "stamp": bool}`.

## Data model

`user_preferences.scan_reading TEXT NOT NULL DEFAULT 'local' CHECK IN ('local', 'checked')`
(migration 0036, `specs/context/db-schema.md`).

## Dependencies

- `LOCAL_VISION_MODEL` (backend: to offer the choice; listener: to run the check) and
  `LOCAL_LLM_URL` for Ollama, both in `.env.example`.
- The check runs in the listener, not the reader: the reader's container cannot reach Ollama on
  the host's `127.0.0.1` (connection refused, measured), and opening Ollama wider would expose an
  unauthenticated model server.

## Edge cases & failure modes

- **Hung model:** one 60 s timeout, then the message's remaining images stay local unasked, so a
  stuck Ollama cannot hold the Pub/Sub callback per image (#86).
- **Preference lookup fails:** images stay local (fail closed), with their text.
- **Database not migrated:** the lookup fails, so the same.
- **Clear page held back:** it loses Gemini's reading, not its content.

## Security & privacy notes

- The local text is unmasked when it leaves the reader and is masked by the listener before
  storage, exactly like text from a text PDF.
- Asking a cloud model whether an image holds a signature would already send it, which is why the
  hackathon's Gemini vision pass cannot be reused.
- Logs and audit rows carry counts and reasons, never the image or the model's text.

## Open questions

- How local OCR compares with Gemini on real, messy scans; and how the check does on them. A real
  signed scan from the team, with consent, is the next measurement.

## Decisions

- 2026-10-10: Two modes, chosen per user: `local` and `checked`. Rationale: the owner wanted both
  ("if company or user wants fully private then use local, if okay with some leaks ... use vision
  model"). Alternatives: local only; vision check only.
- 2026-10-10: `local` is the default, including for users who sent scans to Gemini before.
  Rationale: the check misses about 1 in 10.
- 2026-10-10: `checked` accepts a measured miss rate; the live test guards against regression
  (at most 1 of 12) instead of requiring zero. Rationale: no tested local model reached zero.
- 2026-10-10: The check lives in the listener, not the reader (see Dependencies).
- 2026-10-10: Three questions (signature, face, stamp) instead of one. Rationale: halved Gemma's
  misses; the other prompts tried were worse.
- 2026-10-10: Recommended model Gemma-SEA-LION-v4 4B VL; `gemma4:e2b` is not to be used for this.
- 2026-10-10: Synthetic scans only. Rationale: no real personal documents in the repo.

## Protected decisions

<!-- BEGIN PROTECTED -->
The signature check runs locally, before an image leaves the machine, and fails closed: no model,
no answer or an unclear answer keeps the image here. `local` stays the default.
DO NOT replace it with a cloud vision call, make it fail open, or change the default without the
owner's approval.
<!-- END PROTECTED -->
