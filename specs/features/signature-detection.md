# Signature detection: no signature, face or stamp leaves the machine

- **Status:** draft
- **Owner:** veyroxie (Lane A code; JiaJun to review)
- **Related issue:** epic #138 line 19; extends `attachment-reading.md`
- **Last updated:** 2026-10-10

## Goal

Stop handwritten signatures, faces and ink stamps on ordinary scans from reaching Gemini. The
attachment reader redacts text it can read, but a signature is not text, so today a signed letter
or invoice that passes the reader's gates goes to Gemini with the signature intact.

## User story

As someone whose signed documents arrive by email, I want my signature kept on my company's
machine, so that a cloud model never holds a copy of it.

## Scope

**In scope**
- A third withholding gate in `listener/attachment-reader/reader.py`: after the existing gates
  pass, the redacted image is shown to a local vision model (Ollama) with one yes/no question.
- Yes means the whole image is withheld, like an identity document today. The attachment's
  locally read text is still kept and masked.
- No local vision model configured, or Ollama unreachable, or an unreadable answer: the image is
  withheld (fail closed). The email still ingests.
- A synthetic test set of about 20 made-up scans (blank, signed, stamped, with a photo) to
  measure how many signatures the gate misses.

**Out of scope**
- Boxing out just the signature and sending the rest. A whole-image withhold is simpler and is
  what identity documents already get; partial redaction can come later if too much is withheld.
- Handwriting that is not a signature (notes in a margin).
- Text PDFs, .docx and .xlsx: they return text, never images, so they never reach this gate.

## Acceptance criteria

- [ ] Given a scan with a handwritten signature, when the reader reads it, then the image is not
      in `images` and `skipped_pages` counts it.
- [ ] Given a scan with a face or an ink stamp, when the reader reads it, then the same holds.
- [ ] Given a clean scan with no signature, face or stamp, when the reader reads it, then the
      redacted image is returned as today.
- [ ] Given `LOCAL_VISION_MODEL` is empty, when the reader reads any scan, then no image is
      returned and the reader's text is unchanged.
- [ ] Given Ollama is unreachable or answers something other than the expected JSON, when the
      reader reads a scan, then the image is withheld and a warning is logged with no content.
- [ ] Given the synthetic test set, when the live test runs, then no signed, stamped or photo
      scan is released, and the number of clean scans withheld is reported.

## API surface

No change to `POST /read`. Withheld images already count in `skipped_pages`, which the listener
audits as `withheld` and the admin console shows.

The reader calls Ollama's `POST /api/generate` with `model`, `prompt`, `images` (base64 PNG),
`format: "json"`, `think: false`, `options.temperature: 0`, and expects `{"found": true|false}`.

## Data model

None.

## Dependencies

- Ollama with a vision model. `gemma4:e2b`, the Private mode model, reports the `vision`
  capability (`ollama show`).
- New settings, both read by the reader:
  - `LOCAL_VISION_MODEL`: empty means no local check, so every scanned image is withheld.
  - The Ollama URL, reusing `LOCAL_LLM_URL`. From the container that is
    `http://host.docker.internal:11434`, which needs `extra_hosts: host-gateway` in compose.

## Edge cases & failure modes

- **Cold start:** the first call after Ollama has unloaded the model took 44.5 s (measured
  2026-10-10); warm calls took 0.8 to 3.5 s. The reader's client timeout must exceed the cold
  start, and the listener's 180 s reader timeout still bounds a 20-page scan.
- **Many pages:** one call per released image, up to the reader's 20-page cap.
- **GPU busy or out of memory:** Ollama falls back to the CPU and slows down; the timeout
  withholds the image rather than waiting forever.
- **False positives** (a logo read as a stamp): the image is withheld and only its cloud
  transcription is lost. Missing a signature is the failure that matters, so the prompt leans
  towards "found".

## Security & privacy notes

- The check runs on the redacted image, on the machine, before anything is sent anywhere.
- Asking a cloud model whether an image holds a signature would already send the signature, which
  is why the hackathon's Gemini vision pass (`backend/extract/vision.py`) cannot be reused here.
- Logs carry the outcome only, never the image or the model's text.

## Open questions

- Whether a 2B model misses signatures on real, noisy scans. The synthetic set measures the
  obvious cases; a real signed scan from the team, with consent, would be a better check.

## Out-of-scope future extensions

- Box out only the detected region and send the rest.
- Run the same check on images embedded in email bodies, if those are ever sent to a model.

## Implementation notes

- `Redactor.redact` gains the gate after the format check; `add_image` already counts a `None`.
- Keep the prompt and the expected answer as module constants; parse with `json.loads` and treat
  anything but `{"found": false}` as found.
- Tests: unit tests with a fake Ollama (found, not found, unreachable, malformed, unset model);
  a live test, skipped when Ollama is not running, over the synthetic set.

## Decisions

- 2026-10-10: With no local vision model, scanned images are withheld from Gemini. Rationale:
  the owner chose the safe default. Alternatives: send as today and log it.
- 2026-10-10: One question covers signatures, faces and stamps. Rationale: same call, same cost.
  Alternatives: signatures only.
- 2026-10-10: Test with synthetic scans only. Rationale: no real personal documents in the repo.

## Protected decisions

<!-- BEGIN PROTECTED -->
The signature check runs locally, before an image leaves the machine, and fails closed: no model,
no answer or an unclear answer withholds the image.
DO NOT replace it with a cloud vision call or make it fail open without the owner's approval.
<!-- END PROTECTED -->
