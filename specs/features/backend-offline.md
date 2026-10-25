# Backend offline: the dashboard stays useful after the paid servers are off

- **Status:** in-progress
- **Owner:** veyroxie; Lane D (Han) to review
- **Related issue:** none
- **Last updated:** 2026-10-26

## Goal

The final-year project has ended and the paid Render services are being switched off. Visitors who
open the dashboard (recruiters, the team) should land on the landing page, learn why sign-in is off,
and still see the product: the recorded walkthrough and the demo mailbox, which runs in the browser.

## User story

As a recruiter opening the AIMail link after the project ended, I want to see what it does without an
error screen, so that I can judge the work without the live servers.

## Scope

**In scope**
- A build-time switch, `VITE_BACKEND_OFFLINE=true`, off by default.
- With it on: every dashboard call answers as signed out without touching the network, so the router
  sends visitors to the landing page; the status page still asks the real backend.
- The landing page shows a notice that the project has ended and its paid servers are off, and every
  "Sign in with Google" becomes "Watch the walkthrough" (YouTube); "Try the demo" stays.
- The demo banner drops its "Sign in with Google" button.

**Out of scope**
- The Chrome extension, which talks to the backend directly and needs its own build.
- Hosting the backend anywhere else (`oracle-free-hosting.md` stays parked).

## Acceptance criteria

- [ ] Given the switch is off, when the dashboard is built, then it behaves exactly as before.
- [ ] Given the switch is on, when a visitor opens `/` or any app route, then they land on `/signin`
      with no error screen and no request to the backend.
- [ ] Given the switch is on, when the landing page renders, then it shows the offline notice and no
      "Sign in with Google", and its walkthrough links open the video in a new tab.
- [ ] Given the switch is on, when a visitor presses "Try the demo", then the demo mailbox opens and
      its banner offers only "Leave demo".
- [ ] Given the switch is on, when the page loads, then the browser logs no React hydration errors.
- [ ] The notice, button and closing text exist in English, Malay and Chinese.

## Edge cases & failure modes

- A call rejected before hydration finishes lets the sign-in redirect interrupt it (React #422). The
  offline answer waits the same network pause the demo uses (`src/lib/api/pause.ts`).
- Vercel's build still needs `AIMAIL_BACKEND_ORIGIN` (`nitro.config.ts` refuses to build without
  it); leaving the old Render URL there is harmless, since nothing calls it.

## Security & privacy notes

No email content is involved. The switch is a public feature flag, not a secret, so a `VITE_`
variable is fine.

## Decisions

- 2026-10-26: A build-time switch rather than treating any failed call as signed out. Rationale: a real
  outage would otherwise look like being signed out and hide the error. Alternatives: removing the
  sign-in code, which would make going live again a code change.
