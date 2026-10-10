# Collapse long email bodies

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #175
- **Last updated:** 2026-10-09

## Goal

A long email pushes the AI summary and the draft far down the detail panel. Show the first part of
the body and let the reader expand the rest, without hiding what they are approving a reply to.

## User story

As someone reviewing a draft, I want long emails shortened with a way to read them in full, so
that the summary and the draft stay within reach.

## Scope

**In scope**
- `EmailBody` (dashboard detail panel): the body is capped at about six lines; if it is longer, it
  fades out with a "Show full email" button, which becomes "Show less" once expanded.
- Plain-text, HTML and translated bodies alike.

**Out of scope**
- Earlier/later thread messages (`ConversationMessages`), the extension side panel.
- Remembering the expanded state across emails.

## Acceptance criteria

- [ ] Given a body taller than the cap, when the email opens, then the body is clipped with a fade
      and a "Show full email" button with `aria-expanded="false"`.
- [ ] Given a clipped body, when the reader clicks "Show full email", then the whole body shows,
      the fade is gone, and the button reads "Show less" with `aria-expanded="true"`.
- [ ] Given a body that fits within the cap, when the email opens, then it renders as before with
      no fade and no button.
- [ ] Given a translated body or loaded images, when the reader collapses and expands, then the
      translation and the loaded images stay (nothing is unmounted).
- [ ] Given a new email is opened, then it starts collapsed (`EmailBody` is keyed by email id).
- [ ] Strings exist in `en`, `ms` and `zh`; colours are palette tokens only.

## Dependencies

None.

## Edge cases & failure modes

- Images that load after first paint can make a short body long: the height is re-measured when
  the content resizes.
- Without `ResizeObserver` (old browsers, tests) the body is measured once on render.

## Security & privacy notes

R04 (human approval): the email is never hidden entirely by default; the opening lines are always
visible, and the full text is one click away. The body is also where restored details appear.

## Decisions

- 2026-10-09: Cap the height rather than collapse the whole body by default. Rationale: the reader
  must see what they are approving a reply to (R04). Alternatives: the Lovable prototype's
  fully-collapsed `OriginalEmailToggle`.
