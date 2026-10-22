# Admin and Audit Trail for admins only, and an audit trail admins can read

- **Status:** accepted 2026-10-21 (owner)
- **Owner:** veyroxie (spec, backend); dashboard reviewed by HyperByte12263 (Han)
- **Related issue:** epic #138; ADR 0004 (admin console)
- **Last updated:** 2026-10-21

## Goal

Normal users see their own email and its privacy receipt; they have no use for the company's audit
trail or the admin console, and seeing menu items they cannot open looks unfinished. Show Admin and
Audit Trail to admins only, let admins use their normal Google sign-in for the console, and turn the
audit trail into a structured, company-wide view.

## Decisions (owner, 2026-10-21)

- Users do not get an audit trail; each email's privacy receipt and Changes stay their transparency.
- Admins see everyone's records, with the person and a plain-words action on each row, grouped and filtered.
- Non-admins never see the two menu items. A typed address shows the app's normal "Page not found",
  and the API answers 404, so neither page is revealed to exist.
- Demo mode counts as an admin, so the booth can show the tamper-evident audit trail.

## Scope

**In scope**
- Who is an admin: `app_metadata.role == "admin"` in the Supabase token (`app/core/roles.py`), set by
  `scripts/admin_accounts.py add`. `GET /auth/session` gains `isAdmin`. A newly added admin gets it at
  their next token refresh (within the hour) or by signing in again.
- The admin console accepts the dashboard's Google session cookie for an admin, besides its own
  password session; the console's sign-in form stays as the fallback for password-only admin accounts.
- `GET /audit`: admins and the service token only (404 otherwise). Everyone's rows, each with its person
  (`userEmail`) and group; filters `group`, `person`, `failures_only`, `window` (day, week, month, all);
  `failedRecords` and the list of `people` for the filter.
- Groups (`app/audit_groups.py`): Sending, Drafting, Privacy, Mailbox, Settings, Admin, and Other for
  any action not listed, so nothing is hidden.
- Dashboard: menu items and pages gated on `isAdmin`; the console's own audit table folds into the
  Audit Trail page; the page gains a summary line, a filter row, person and group on each row.

**Out of scope**
- Paging past 100 rows and CSV export (later).

## Acceptance criteria

- [ ] Given a non-admin, then neither menu shows Admin or Audit Trail, `/admin` and `/audit` show the
      normal not-found page, and `GET /audit` answers 404.
- [ ] Given an admin signed in with Google, then both show, and the console opens without its own sign-in.
- [ ] Given filters, then they reach SQL as bound values (no string pasting) and return the right rows on
      Postgres; each row names its person.
- [ ] Given demo mode, then both pages show with demo records.

## Security

The role is checked on the server for every audit and console call; hiding links is only presentation.
The console still requires its admin header on state-changing calls, and the dashboard cookie is
HttpOnly and SameSite=Strict as before.
