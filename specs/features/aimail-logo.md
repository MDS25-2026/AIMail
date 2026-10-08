# AIMail logo in the header, favicon and extension toolbar

- **Status:** in-progress
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #174
- **Last updated:** 2026-10-08

## Goal

The dashboard header is plain text and the extension's toolbar icon is a generated envelope. Use
the AIMail logo art from the Lane D prototype, so every screen (and the poster's UI screenshots)
carries the brand.

## User story

As a reader of the dashboard or the Chrome toolbar, I want to see the AIMail logo, so that I can
recognise the product at a glance.

## Scope

**In scope**
- Header wordmark in `AppShell`, one variant per theme.
- `public/favicon.ico` and `extension-public/icons/icon-{16,48,128}.png` from the square "AI" glyph.
- Retire `scripts/make-extension-icons.py`, which would overwrite the icons.

**Out of scope**
- The side panel's own header, the sign-in and admin pages.
- Any change to the palette tokens.

## Acceptance criteria

- [ ] Given the light theme, when any dashboard page loads, then the header shows the wordmark
      with dark "mail" text and the dark-theme variant is not displayed.
- [ ] Given the dark theme (`dark` class on `<html>`), when any dashboard page loads, then the
      header shows the wordmark with light "mail" text and the light-theme variant is not displayed.
- [ ] The visible logo has alt text equal to `app.name` ("AIMail"); the tagline still shows.
- [ ] The browser tab shows the "AI" glyph (`favicon.ico` with 16, 32 and 48 px entries).
- [ ] `make extension` produces a toolbar icon of the "AI" glyph at 16, 48 and 128 px.
- [ ] `scripts/make-extension-icons.py` no longer exists, and the README describes the icon files.
- [ ] `tsc`, eslint, vitest, the production build and the palette check pass.

## Dependencies

None.

## Edge cases & failure modes

- At 16 px the glyph is small but legible; the full wordmark is never used at icon sizes.

## Security & privacy notes

Static assets only.

## Decisions

- 2026-10-08: Two `<img>` elements toggled by the `dark:` variant rather than one image swapped in
  script. Rationale: the theme class is set server-side, so the right logo is in the first paint
  with no flash. Alternatives: a CSS background swap (loses alt text).
- 2026-10-08: Delete `make-extension-icons.py` rather than teach it to resize the art. Rationale:
  it needs no reruns now the icons are fixed artwork; keeping it invites an overwrite.
