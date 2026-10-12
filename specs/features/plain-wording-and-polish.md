# Plain wording, mark unread, and polish

- **Status:** built 2026-10-11 (in review)
- **Owner:** veyroxie (Hanif to review the review-reason codes in `email_agent.py`)
- **Related issue:** epic #138, Phase 2 lines 67, 69, 70, 71 and 72
- **Last updated:** 2026-10-11

## Goal

Say what AIMail means in words a non-engineer understands, and finish the small gaps a user
notices: why a draft was flagged, which emails they have not dealt with, the error page in their
language, and a dashboard that works by keyboard and screen reader.

## User story

As someone reviewing drafts, I want to see in plain words why a draft needs my attention, mark an
email unread to come back to it, and use AIMail in Malay or Chinese without English slipping
through.

## Scope

**In scope**
- **Review reasons as codes.** The agent emits a stable code beside each free-text reason
  (`low_confidence`, `phishing_link`, `not_grounded`, `pii_found`, `figures_not_in_source`,
  `critic_unavailable`, `grounding_failed`, `does_not_address`, `refine_rounds`, `repair_stopped`),
  plus the backend's own `no_draft`. Each carries its items where it has them (the PII entity
  types, the figures, the unanswered points). The free text stays for the admin console and the
  audit. Rows stored before this change are mapped by prefix in one place, with "flagged for
  review" as the fallback.
- **The email view** lists the reasons in words, visible on the page (no tooltip-only text); the
  To-do page shows the first reason on each "needs review" row.
- **The critic badge** reads "AI check passed" or "AI check: review suggested", with the
  confidence in words beside it ("92% sure"), instead of "Critic 72%".
- **The error page** in the reader's language (from the language cookie), English otherwise.
- **Mark unread** from the email view and the inbox row; the email stays unread until it is opened
  again (opening it does not immediately mark it read again). In the email view it is a toggle:
  once unread, the same place offers **Mark read**, which marks it read through the usual open-email
  call (2026-10-12, test run T10: the button used to vanish after one use).
- **Source highlighting** works for Chinese (sentences end at 。！？ with no space, and matching
  uses character pairs, since Chinese has no spaces between words) and ignores common Malay words.
- **Accessibility:** a "Skip to content" link, one `h1` per page with headings in order, and focus
  moved to the page heading after navigating.
- **Malay labels that fit:** no clipped or overflowing labels at 375px and 1280px in Malay.

**Out of scope**
- Showing the original email fetched live from Gmail (epic line 68): it would put unmasked content
  in the dashboard, which is a privacy decision for the owner, not polish.
- A welcome tour: deferred, so the dashboard stays as the award poster shows it.
- Paging on Sent and Drafts (epic line 71): already done; both lists page through older mail with
  the inbox's own "Load older emails".
- The unread count in the navigation: Han's issue #171.

## Acceptance criteria

- [x] Given a draft flagged for low confidence and an unanswered point, then the email view says
      so in words in all three languages, and lists the point.
- [x] Given a row stored before the codes existed, then its reasons still show in words, or as
      "flagged for review" when unrecognised.
- [x] Given the To-do page, then each "needs review" row shows its first reason (todo-page.md's
      "with its reason" box).
- [x] No PII value is ever shown as a reason: PII reasons list entity types only.
- [x] Given an opened email, when the user marks it unread, then it shows unread in the list and
      stays unread after the view refreshes.
- [x] Given a Chinese policy passage and a Chinese draft that quotes it, then the quoted sentence
      is highlighted.
- [x] Given the error page with the language cookie set to Malay or Chinese, then it reads in that
      language.
- [x] Every page has one `h1`, a skip link reaches the main content, and after navigating, focus is
      on the new page's heading.

## API surface

- The agent's `/process-email` and `/refine` responses add `review_codes: [{code, items}]` beside
  `review_reasons` (`agent_contract.py`).
- `DashboardEmail` adds `reviewReasons: [{code, items}]`.
- `POST /emails/{id}/unread` (`204`) sets `read_at` back to null for the caller's own email (`404`
  otherwise).

## Data model

No migration: codes are stored inside the existing `critic_checks` JSON as `review_codes`.

## Edge cases & failure modes

- **An unknown code from a newer agent:** shown as "flagged for review", never as the raw code.
- **Mark unread on a sent email:** allowed; it only changes the reading state.
- **The error page before any cookie is set:** English.

## Security & privacy notes

- PII reasons carry entity types (PERSON, MY_NRIC), never the matched text; the agent already
  reports types only (`scan_draft_pii`).
- Unanswered points are masked action items; they are shown through the same detail restoration as
  the rest of the email, so hide details applies.

## Decisions

- 2026-10-11: Codes are emitted by the agent beside the text, not parsed from the text by the
  dashboard. Rationale: parsing breaks silently whenever a reason is reworded.
- 2026-10-11: Showing the original email live from Gmail is left to the owner (privacy model).
- 2026-10-11: Opening an email marks it read; a separate `read_email` does that, and `email_detail`
  never does, so mark unread is not undone by the open view refreshing.
- 2026-10-11: Leaving an email during the undo window sends it (from #211); tests that end with a
  countdown running now cancel it, or unmounting would send it into the next test.
