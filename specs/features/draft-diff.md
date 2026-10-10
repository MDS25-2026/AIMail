# Show what changed in the draft

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #149
- **Last updated:** 2026-10-10

## Goal

The reader approves a reply that is part AI, part their own edits, but the draft box shows only
the result. Let them see, word by word, what they changed from the AI draft and what a Refine
changed, so the human-in-the-loop step is visible.

## User story

As someone reviewing a draft, I want to switch to a view that marks what was added and removed,
so that I know exactly which words are mine and which the AI wrote or rewrote before I send.

## Scope

**In scope**
- `DraftReplyEditor` (dashboard detail panel and extension side panel): a `Draft | Changes`
  toggle. Changes replaces the text box with a read-only, word-level diff: added words on
  `success-soft` and underlined, removed words on `danger-soft` and struck through.
- One comparison at a time, always the most recent change:
  - **Your edits:** the stored AI draft → the text in the box, once the reader has typed.
  - **Last Refine:** the text the Refine was given → the draft it returned, until the reader types
    or the draft is regenerated.
- A caption naming the comparison, a legend (Added / Removed), and a "No changes" message.
- `diff` (jsdiff 8, BSD-3, own types) added as a direct dependency; it is already installed
  through `@tanstack/router-utils`.

**Out of scope**
- Persisting the pre-Refine text: it lives in the page's memory, so a reload shows only edits.
- A history of every version, side-by-side view, character-level diff.
- Any backend or API change.

## Acceptance criteria

- [ ] Given an AI draft and no edits, when the reader opens Changes, then it says there are no
      changes from the AI draft.
- [ ] Given the reader edited the draft, when they open Changes, then the caption reads "Your edits
      to the AI draft", inserted words are in `<ins>` and deleted words in `<del>`, and unchanged
      words are plain.
- [ ] Given a Refine succeeded and the reader has not typed since, when they open Changes, then the
      caption reads "What Refine changed" and the diff runs from the text sent to Refine to the
      refined draft.
- [ ] Given that state, when the reader types, then Changes compares the refined draft with their
      edits; when the draft is regenerated, the Refine comparison is dropped.
- [ ] Given Changes is open, then the draft cannot be edited there; switching back to Draft shows
      the text box with the same text. The toggle buttons expose `aria-pressed`.
- [ ] Given another email is opened, then the panel starts on Draft.
- [ ] Added and removed words are told apart without colour (underline vs strike-through) and to
      screen readers (`<ins>`/`<del>` plus hidden "added"/"removed" text).
- [ ] Strings exist in `en`, `ms` and `zh`; colours are palette tokens only.

## API surface

None. `useDraftWorkflow` gains `comparison: { before: string; after: string; source: "edits" |
"refine" }`; `lib/draftDiff.ts` exports `diffDraft(before, after)` returning
`{ text, kind: "same" | "added" | "removed" }[]`.

## Data model

None.

## Dependencies

`diff@^8.0.4` (npm). Refine and regenerate as they are (`useDraftWorkflow`).

## Edge cases & failure modes

- A failed Refine leaves the previous comparison as it was.
- Toggling "hide details" between a Refine and opening Changes compares masked with restored text,
  so placeholders show as changed. Rare; documented, not handled.
- Long drafts: jsdiff's word diff is fast for email-length text; nothing is computed until Changes
  is open.

## Security & privacy notes

Client-side only: both texts are already on screen, and nothing new is sent or stored. R04 (human
approval) is strengthened: the reader sees exactly what the AI wrote before sending.

## Decisions

- 2026-10-10: Use jsdiff (`diffWords`) rather than our own LCS. Rationale: tested edge cases
  (whitespace, punctuation) for a few lines of code. Alternatives: hand-written word LCS.
- 2026-10-10: Show only the most recent change, not a version history. Rationale: covers both
  #149 criteria with one piece of in-memory state. Alternatives: storing every version server-side.
