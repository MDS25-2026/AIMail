# Sender verification and the audit hash chain

Status: built 2026-10-07 (issue #148; PR #161 by Hanif, review fixes in `feat/holding-reply`).

## Goal

Never draft or send an automatic answer to an email whose sender failed domain checks, and give
each user a record of what AIMail did for them that shows when a record was changed or removed.

## Scope

**Sender verification**
- The listener reads every `Authentication-Results` header. `spf=fail`, `dkim=fail` or
  `dmarc=fail` stores `messages.auth_status = spoof_detected`; otherwise `pass`. `softfail` and
  `none` are not failures.
- A `spoof_detected` email is never drafted (background drafter, opening it, regenerate, refine),
  never sent (`409 sender_unverified`) and never gets a holding reply (`Refusal.SPOOFED`).
- Mailing lists and forwarding often break DKIM, so the owner can confirm a sender:
  `POST /emails/{id}/confirm-sender` moves `spoof_detected` to `sender_confirmed` (only that
  transition), resets the drafting attempts, and is audited. Drafting then resumes.

**Audit hash chain**
- A trigger (migration 0024) gives each new `audit_log` row a `chain_seq`, the previous row's
  hash as `prev_hash`, and `current_hash = SHA-256` over `prev_hash`, `chain_seq`, action,
  detail, success, user and time, separated by `chr(31)` (`audit_row_hash()`).
- Writers are serialised by a transaction advisory lock, not `LOCK TABLE`, which deadlocked against
  the insert's own lock.
- `GET /audit` checks the whole chain: every row's hash, every link to the row before, and no gap
  in `chain_seq`. It returns `is_chain_intact`, the head hash, and the caller's own rows.
- Each `audit()` call made for a user records `user_id`. A person sees only their rows; rows with
  no owner (the listener's pipeline events, admin sign-ins) are for scripts and admins.

**Out of scope**
- A keyed hash (HMAC). The key would have to live outside the database, and the listener writes
  through PostgREST.
- Showing ownerless rows in the admin console.
- Owners on the listener's audit rows.

## Acceptance criteria

- [x] Given a failed SPF, DKIM or DMARC result, then the email is stored `spoof_detected`.
- [x] Given a `spoof_detected` email, then opening it, the poller, regenerate and refine never
      call the agent; send answers `409 sender_unverified`; no holding reply is scheduled.
- [x] Given a confirmed sender, then the email is drafted again; confirming a passing email
      changes nothing.
- [x] Given concurrent audit writes, then no row is lost and the chain has no gap (10 at once,
      live, 2026-10-07).
- [x] Given an edited or deleted middle row, then `is_chain_intact` is false (live, in a
      rolled-back transaction).
- [x] Given two users, then each sees only their own audit rows.

## Ledger rules (2026-10-08, migration 0025)

- **Append-only:** a trigger refuses UPDATE and DELETE on `audit_log`, for every role.
- **No foreign key under the hash:** `user_id` stays, opaque, after an account is deleted, so deletion no
  longer rewrites rows or breaks the chain, and the deletion's own row is written.
- **Structured:** `detail` is compact JSON of fields from one action list (`app/audit.py`, `AuditAction`;
  the listener uses the same names). The API returns it parsed as `fields`.
- **Same transaction where it matters:** a send's row and a sender confirmation's row commit with the
  change they record (`record(session, ...)`); other rows are written on their own and a failed write is
  logged.
- **Three states:** each row is `verified`, `tampered` or `unverifiable` (written before the chain);
  unverifiable is never shown as verified.

## Limitations (say these on the poster too)

- Anyone with full database rights can rebuild the whole chain. Recording the head hash outside
  the database (an export, a printout) is what catches that.
- Deleting the newest rows leaves a shorter, valid chain; only a recorded head hash shows it.
- Rows written before migration 0024 are not in the chain and show as unverified.

## Data model

See [`../context/db-schema.md`](../context/db-schema.md): `messages.auth_status`, and
`audit_log.user_id`, `prev_hash`, `current_hash`, `chain_seq`.
