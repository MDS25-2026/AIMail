# Works on a phone: mobile layout and install as an app

- **Status:** built (in review)
- **Owner:** veyroxie (dashboard code; Han to review)
- **Related issue:** #157 (epic #138, line 67)
- **Last updated:** 2026-10-11

## Goal

Review, approve and send drafts from a phone: on the train, between meetings. Today the dashboard
is a fixed 320px inbox column beside the email, which does not fit a phone screen.

## User story

As someone away from my desk, I want to open AIMail on my phone, read an email, check the draft and
send it with my thumb, so that replies do not wait until I am back at a laptop.

## Scope

**In scope**, below 768px (Tailwind `md`); desktop unchanged:
- **Inbox:** full screen. Tapping an email opens it full screen; a back arrow returns to the list
  at the same scroll position. The URL (`?email=`) drives which view shows, so the phone's back
  button works too.
- **Email and draft:** readable type, the draft editor full width, and Send, Edit and Regenerate
  in a bar fixed to the bottom.
- **Bottom navigation:** Inbox, To-do (with its count, `todo-page.md`), Sent, Settings.
- **Touch targets** at least 44 by 44px.
- **Pages:** inbox, email and draft, To-do, Sent and Settings are designed for the phone. The
  other pages (drafts, knowledge, audit) must not scroll sideways but are not redesigned. The admin
  console stays desktop only.
- **Install as an app:** a web app manifest (name, icons from `aimail-logo.md`, theme colour,
  `display: standalone`), so "Add to home screen" opens AIMail without the browser bar.

**Out of scope**
- Swipe gestures (tap only for now).
- Offline mode, a service worker, push notifications.
- A native app.

## Acceptance criteria

- [x] Given a 375px-wide screen, when the inbox loads, then the list fills the width and nothing
      scrolls sideways.
- [x] Given a 375px screen, when the user taps an email, then the email and its draft fill the
      screen, and the back arrow and the phone's back button both return to the list at the same
      position. (Checked in a headless browser at 320 and 375px, in all three languages.)
- [x] Given an open draft on a phone, then Send, Edit and Regenerate are visible in the bottom bar
      without scrolling, and the keyboard does not cover the editor.
- [x] Given any phone page, then every button and link is at least 44 by 44px.
- [x] Given a 375px screen, then the bottom navigation shows Inbox, To-do with its count, Sent and
      Settings, and the current page is marked (not by colour alone).
- [x] Given drafts, knowledge or audit on a 375px screen, then nothing scrolls sideways.
- [x] Given a 1280px screen, then the layout is as before.
- [ ] Given Chrome on Android or Safari on iOS, when the user chooses "Add to home screen", then
      AIMail installs with its icon and opens without the browser bar. (Manifest and icons are
      checked by a test; not yet tried on a real phone.)
- [x] The existing palette and contrast check passes, in light and dark mode.

## API surface

None. The manifest is a static file served with the dashboard.

## Data model

None.

## Dependencies

- `aimail-logo.md` for the icons (192px and 512px, plus a maskable one).
- `todo-page.md` for the To-do count in the navigation.
- The existing three languages: bottom navigation labels fit in Malay, the longest.

## Edge cases & failure modes

- **Long Malay labels** in the bottom bar: icon plus a short label; the full name as the
  accessible name.
- **The on-screen keyboard** shrinks the viewport: the bottom bar sits above it, the editor
  scrolls.
- **Notched phones:** safe-area insets on the bottom bar.
- **Rotating to landscape:** below 768px stays the phone layout.
- **Sign-in on a phone:** the Google sign-in redirect returns to the installed app's window.

## Security & privacy notes

- No change: same cookies and session. The installed app is the same site in its own window.
- A phone is more easily seen by others; the existing "hide details" toggle from restorable
  masking matters more here, so it stays one tap away on the email view.

## Decisions

- 2026-10-10: Tap only, no swipe gestures. Rationale: swipes are hidden, need a tap alternative
  anyway, and add a gesture library.
- 2026-10-10: Installable through a manifest, no service worker or push. Rationale: an app icon
  for the pitch at almost no cost.
- 2026-10-10: Phone pages are inbox, email and draft, To-do, Sent and Settings; the admin console
  stays desktop only.
- 2026-10-11: An open email hides the bottom tabs, and its Send bar takes the bottom. Rationale:
  the screen is too short for both bars; Gmail's app does the same, and back returns to the tabs.
- 2026-10-11: On a phone, Regenerate shows its icon only (its name stays for screen readers), and
  the "nothing is sent until you approve" line is hidden. Rationale: Regenerate, Send later and
  Approve & Send then fit one row at 375px; Approve & Send already says the second.
- 2026-10-11: The keyboard resizes the page (`interactive-widget=resizes-content`), so the Send
  bar rides above it on Android. Safari on iOS ignores this and keeps the bar under the keyboard
  while typing; the editor itself stays visible.
- 2026-10-11: The install icons are the 128px extension glyph scaled up (slightly soft at 512px)
  until the original artwork is found.
