# Chrome extension: AIMail beside the email in Gmail

- **Status:** accepted by the owner 2026-10-05 ("build it, extension then C"); Lane D, built by
  veyroxie with Han informed
- **Owner:** veyroxie; Lane D (Han) owns the folder
- **Related:** proposal Goal 1; [ADR 0005](../../docs/adr/0005-dashboard-google-sign-in.md) (the
  extension was planned as a session client); [restorable-masking.md](./restorable-masking.md)
  (the panel shows the same `details`); `docs/backlog.md` ("nothing should displace the extension")
- **Last updated:** 2026-10-05

## Goal

Reading an email in Gmail, the user opens AIMail's panel beside it and sees the summary, the action
items and a draft reply for *that* email, refines it and approves it, without leaving Gmail. The
original email, with every detail, is the one Gmail is already showing.

## User story

As a support agent working in Gmail, I click the AIMail icon once; from then on the panel follows
whichever email I open and has a reply ready, so I approve and move on.

## Scope

**In scope**
- A Manifest V3 Chrome extension using Chrome's side panel, enabled only on `mail.google.com`.
- Following the open email: a content script reads the open thread's id from Gmail's page and tells
  the panel when it changes.
- A backend route returning the email for a Gmail thread id, scoped to the signed-in user.
- The panel: the dashboard's existing draft components, rearranged for a narrow, streamlined panel.
- Sign-in by the dashboard's session: signed in once in the dashboard, the panel works; signed out,
  one button opens sign-in in a tab.
- Built from the dashboard project with no new dependency; `make extension` produces a folder to
  load unpacked and a zip to hand out.

**Out of scope**
- Chrome Web Store publishing (unpacked for now; Unlisted later is an operational step).
- Outlook (team-owned).
- Writing into Gmail's own compose box: AIMail sends through its backend as the dashboard does, so
  the human-approval record, masking checks and audit trail stay in one place.

## How it works

```
 Gmail tab (mail.google.com)                      Side panel (extension page)
 ┌───────────────────────────────┐   thread id   ┌────────────────────────────────┐
 │ content script: watches the   │──────────────►│ GET /emails/by-thread/{id}     │
 │ open thread (data-legacy-     │◄──────────────│   (session cookie, same API)   │
 │ thread-id, URL fallback)      │  "which one?" │ summary · actions · draft      │
 └───────────────────────────────┘               │ [Refine]  [Approve & Send]     │
                                                 └────────────────────────────────┘
```

1. **The open thread.** Gmail marks the open conversation's subject with `data-legacy-thread-id`,
   the same hex id the Gmail API uses (`messages.thread_id`). The content script reads it, falls back
   to `data-thread-perm-id` (`thread-f:<decimal>`, converted to hex) and then to a hex id at the end
   of the URL. It watches `hashchange` and DOM changes (debounced), and reports only when the id
   changes, including to "none" when the user goes back to the inbox list. It reads nothing else
   from the page.
2. **The panel asks and listens.** On opening, and when the active tab changes, the panel asks the
   content script for the current id; it also listens for change reports.
3. **The route.** `GET /emails/by-thread/{thread_id}` returns the newest message in that thread
   owned by the signed-in user, as the detail view does (generating the draft if needed); `404` when
   AIMail has none (an older email, the Sent folder, or another Gmail account). Same scope rules as
   every email route.
4. **Auth.** The panel calls the backend with the dashboard's HttpOnly session cookie. Chrome sends
   it because the extension holds host permission for the backend's address; the CSRF header is
   sent as the dashboard does. No token is stored in the extension. A `401` shows the sign-in
   state, whose button opens the backend's Google sign-in in a tab.
5. **Panel states**, each one screen: not Gmail ("Open Gmail to use AIMail"), no email open ("Open
   an email"), loading, signed out, not found ("AIMail hasn't received this email", with the signed-in
   address so a different Gmail account is obvious), quarantined (existing notice), and the email.
6. **Streamlined layout.** Header: AIMail and the signed-in address. Body: subject, summary, action
   items, then the draft editor taking the remaining height, the tone switch and refine box beside
   it. Footer: Regenerate and a full-width Approve & Send. The thread list is left out (Gmail shows
   the thread); sources collapse to one line. The panel fills Chrome's resizable side panel width.
   Language follows the browser (English, Malay, Chinese); theme follows the system.
7. **One component.** The dashboard's `/extension` preview renders the same panel component, so the
   preview is the real thing.

## Manifest

- `side_panel.default_path`, `background.service_worker`, one content script on
  `https://mail.google.com/*`.
- Permissions: `sidePanel`. Host permissions: `https://mail.google.com/*` (content script) and the
  backend's origin, taken from `VITE_BACKEND_URL` at build time (no hard-coded host).
- The panel opens from the toolbar icon and is enabled only on Gmail tabs.

## Security & privacy

- The content script reads one attribute (the thread id) and the URL; it never reads or sends email
  content. Everything shown comes from the backend, masked as today.
- No credential is stored in the extension; the session stays in the backend's HttpOnly cookie.
- The extension page is not reachable by web pages (no `web_accessible_resources`).
- Content Security Policy: Manifest V3's default (no remote code, no inline script).

## Acceptance criteria

- [ ] With the dashboard signed in, opening an email in Gmail shows its summary and draft in the
      panel within a second when the draft exists, and the generating state otherwise.
- [ ] Opening another email switches the panel; going back to the inbox shows "Open an email".
- [ ] Refine, tone, Regenerate and Approve & Send work as in the dashboard, with the same warnings.
- [ ] Signed out, the panel offers sign-in; after signing in, it works without reloading the extension.
- [ ] An email AIMail does not have, or one from another Gmail account, shows the not-found state,
      never someone else's email.
- [ ] `make extension` builds a loadable folder and a zip; Chromium loads it with no errors.

## Test plan

- Unit: thread id extraction (legacy attribute, perm id conversion, URL fallback, none).
- Backend: the route returns the newest owned message in the thread; 404 for another user's thread
  and for an unknown one.
- Build: Chromium loads the unpacked build; the service worker registers with no errors.
- Live (owner): the 5 Oct test thread in Gmail, end to end.

## Estimate

About three days, including the layout pass.
