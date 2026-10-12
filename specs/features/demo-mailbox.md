# Demo mailbox: try AIMail without signing in

- **Status:** in progress (first slice: switch, entry and exit, four emails, pretend Send)
- **Owner:** HyperByte12263 (Han, Lane D)
- **Related issue:** #227
- **Last updated:** 2026-10-12

## Goal

Let anyone who scans the poster's QR code use AIMail in under a minute, with no account. Today the
only way in is Sign in with Google, and our Google app is in testing mode (#160), so a judge's own
Gmail is refused unless they are a listed test user. A built-in demo mailbox removes both problems.

## User story

As a judge or visitor at the showcase, I want to open AIMail and click through a real-looking inbox
straight away, so that I can see what it does without an account or my own email.

## Scope

**In scope**
- **Entry:** a **Try the demo** button beside Sign in with Google on the landing page (`/signin`):
  in the hero, the header and the closing call to action. It turns demo mode on and opens the inbox.
- **Demo mode answers every dashboard call itself.** `request()` in `lib/api/client.ts` hands the
  call to `src/demo/` instead of `fetch`, so no page changes and nothing reaches the backend. The one
  exception is `GET /service-status` (the public `/status` page): it needs no sign-in and carries no
  mailbox data, and refusing it made every part read "Not working" (2026-10-13).
- **Demo data, bundled and fictional** (made-up Malaysian companies and people):
  - About 12 emails across critical, urgent, medium and low; all six categories; English, Malay
    and Chinese; a few threads with more than one message.
  - Each with its summary, action items, a draft, checker confidence, masked placeholders and the
    privacy receipt that goes with them.
  - To-do items in each section, audit log entries, two or three templates, a few company documents
    for Knowledge, and default settings.
- **AI actions without a model:** Refine, Regenerate (per tone), Translate and template Adapt return
  answers written in advance for each demo email. Changes view (#149) then shows what changed.
- **Send is pretend:** the email moves to Sent and an audit entry is added; nothing leaves the
  page. Schedule, snooze, dismiss and mark unread work the same way, in memory.
- **A demo banner on every dashboard page:** "Demo mailbox: made-up emails, nothing is sent", with
  Sign in with Google and Leave demo. Sign out in the account menu also leaves the demo.
- Strings in `en`, `ms` and `zh`.

**Out of scope**
- The Gmail extension (needs real Gmail). The `/extension` preview page shows demo data for free,
  because it also goes through `request()`.
- The admin console (its own sign-in) and inbox search / thread Q&A: in demo mode they say
  "Not available in the demo".
- Uploading documents or attachments, writing-profile learning, Google account actions
  (disconnect Gmail, delete account): "Not available in the demo".
- Any backend, API or database change.

## Acceptance criteria

- [ ] Given a signed-out visitor on `/signin`, when they click **Try the demo**, then the inbox opens
      with the demo emails, sorted most urgent first, and no sign-in is asked for.
- [ ] Given demo mode, when any dashboard page loads or any button is used, then no request is made
      to the backend (`fetch` is never called for an API path) and no model is called.
- [ ] Given demo mode, then every dashboard page shows the demo banner; **Leave demo** and **Sign
      out** return to `/signin` with demo mode off.
- [ ] Given a demo email, when the visitor clicks Send, then it moves to Sent with an audit entry,
      the banner's "nothing is sent" stays true, and no request leaves the page.
- [ ] Given a demo email, when the visitor uses Refine, Regenerate or Translate, then the draft
      changes to the prepared answer, and Changes shows the difference.
- [ ] Given a demo email with masked details, when the visitor opens the privacy receipt, then it
      shows what the AI saw and what stayed with the user.
- [ ] Given changes made in the demo, when the page is reloaded, then the demo data is back as it
      started and the visitor is still in demo mode; closing the tab ends demo mode.
- [ ] Given a demo-mode call the demo does not support, then the page shows "Not available in the
      demo" rather than an error or a sign-in redirect.
- [ ] Given a visitor who signs in with Google from the banner, then demo mode is off and they see
      their own mailbox only.
- [ ] Demo content contains no real person's details; strings exist in `en`, `ms` and `zh`; colours
      are palette tokens only.

## API surface

None on the backend. In the dashboard:
- `src/demo/` exports `isDemo()`, `startDemo()`, `leaveDemo()` and
  `demoRequest<T>(path, options): Promise<T>`, which `request()` calls first when `isDemo()`.
- Demo answers use the same types as the real API (`schema.gen.ts`), so a drift fails to compile.
- One new `ApiErrorCode`, `NotInDemo`, for unsupported calls.

## Data model

None. Demo changes live in memory for the tab; the demo flag lives in `sessionStorage`.

## Dependencies

- #219 landing page (the button goes there). #149 Changes view, #210 To-do, #207 templates, #213
  sort: shown with demo data, unchanged.

## Edge cases & failure modes

- **Storage blocked** (private mode, strict settings): the flag falls back to memory, so the demo
  still works until reload.
- **Back on the landing page** (browser Back, or typing `/signin`): the visitor is out of the demo,
  and its emails are cleared from memory. The landing page is the front door, never part of the demo.
- **Signed-in visitor clicks a demo link:** demo mode only starts from the button; a signed-in
  visitor never sees it on `/signin`, and the real session is untouched.
- **Server render:** the page is server-rendered but loads data only in the browser. The banner
  renders after mount, so the server's first paint and the browser agree.
- **New endpoints added later:** an unknown path answers "Not available in the demo", never a
  network call. A test lists every path the dashboard calls and checks each is handled or refused.
- **Polling** (session, inbox): answered locally, so it costs nothing.
- **Answers that land too fast:** demo answers wait 150 ms, as a network call would. Answered at
  once, the session landed before the page finished hydrating and React reported a mismatch.

## Security & privacy notes

- Demo mode never sends a mailbox request, so it cannot reach anyone's real data, and it does not
  weaken sign-in for real users: the backend is unchanged. Its only call out is the public status
  check, which answers the same for everyone.
- All demo content is invented. Placeholders show masking as the real flow does; the "real" values
  behind them are invented too.
- No model is called, so the public demo cannot run up Gemini costs or be used as a free AI.

## Open questions

- Showcase date: sets how much demo content to write.
- Should one team member review the demo emails for realism and tone (and the Malay and Chinese
  ones for language)?

## Out-of-scope future extensions

- A guided tour over the demo (step 1: the inbox, step 2: the privacy receipt...).
- A shared, read-only live demo account on the backend for the extension.

## Implementation notes

- `request()` gains one guard at the top: `if (isDemo()) return demoRequest<T>(path, options);`.
- Keep demo data in typed `.ts` files under `src/demo/data/`, one file per area (emails, todo,
  audit, templates, documents, settings), so content can be reviewed separately from logic.
- Route matching: a small table of `{ method, pattern, handler }`, not a chain of `if`s.
- Entering and leaving go through `useDemoSwitch()` in `lib/queries/session.ts`, which also empties
  the query cache, so demo emails never sit beside a real mailbox's.
- Build order: (1) switch, guard, entry, banner, four emails, pretend Send and snooze/schedule;
  (2) the rest of the emails and the prepared AI answers; (3) To-do, Audit, Templates, Knowledge
  and Settings data. Until (3), those pages say "Not available in the demo".
- Prepared AI answers: keyed by email id and action (`refine`, `regenerate:<tone>`,
  `translate:<lang>`); a missing one answers `NotInDemo`.
