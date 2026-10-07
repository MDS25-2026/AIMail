# Privacy receipt and hidden-detail chips

Status: built 2026-10-07 (issue #158). Dashboard only; no API change.

## Goal

Make masking visible: show the reader what the AI was given, what stayed with them, and let
them fill in a detail the AI never saw without leaving the draft.

## Scope

- **Privacy receipt:** a "Privacy receipt" button in the email header opens a dialog with
  - how many details of each kind were hidden (a person named three times counts once);
  - "What the AI was given": the email body exactly as stored and sent, with placeholders;
  - "What stayed with you": each placeholder and its real value, from the sealed vault
    (restorable-masking.md). With "Hide details" on, values show as their kind only;
  - a line saying the thread, policy passages and writing style go the same way, masked.
- **Hidden-detail chips:** under the draft, one chip per detail that will not be filled in at
  send: a redaction marker (`[Redacted]`, `(hidden)`, `(name)`) or a placeholder with no known
  value. Tapping one explains it and takes the real value, which replaces that one spot.

**Out of scope:** the exact prompt (it is not stored); the model that drafted it.

## Acceptance criteria

- [x] The receipt's "given to the AI" text is the stored masked body, unchanged.
- [x] Counts group by kind and count each placeholder once.
- [x] Chips list only details that will not be filled in, in reading order; a placeholder the
      vault can fill is not a chip.
- [x] Filling a chip replaces one occurrence; an empty value changes nothing.
