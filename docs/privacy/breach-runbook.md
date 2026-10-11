# Suspected data breach: runbook

What to do, in order, when someone suspects that personal data in AIMail was exposed, changed or
lost. Every step names the part of this system it uses. Record everything in
[`breach-register.md`](breach-register.md) as you go.

The order matters: **preserve evidence before you erase anything.** Disconnecting Gmail and deleting
an account both delete data (`backend/app/erasure.py`), and that data may be what shows what
happened.

## Legal duty, in general terms

The Personal Data Protection (Amendment) Act 2024 introduced mandatory data breach notification in
Malaysia: a data controller must notify the Personal Data Protection Commissioner of a personal
data breach, and must notify affected individuals where the breach is likely to cause them
significant harm. **Confirm the current requirements and deadlines with the university or a legal
adviser.** This runbook does not quote deadlines; treat notification as urgent from the moment a
breach is confirmed.

## 1. Record and assign (first hour)

1. Open a row in the breach register: date found, who found it, what was seen.
2. Name one person to lead and one to keep the log. Tell the project supervisor.
3. Write down what is known and what is assumed, separately. Do not paste secret values, email
   bodies or personal details into chat, issues or the register.

## 2. Preserve evidence

Do this before any containment step that deletes data.

1. **Check the audit chain.** `audit_log` is append-only (a trigger from migration 0025 refuses
   every UPDATE and DELETE) and hash-chained (migration 0024): each row's `current_hash` covers its
   own fields and the previous row's hash.
   - From `backend/`: `../.venv/bin/python scripts/verify_audit_chain.py`. It prints each broken
     row (`[BROKEN] seq ... id ... action ...`), the number of chained records and the head hash,
     and exits 1 if the chain is broken.
   - Or call `GET /audit` with the `BACKEND_API_TOKEN` bearer token: `isChainIntact`,
     `totalRecords`, `verifiedRecords`, `headHash`. A signed-in user sees only their own rows; the
     chain verdict is always over the whole table.
   - Rows written before migration 0024 have no `chain_seq` and are reported as unverifiable, not
     verified.
   - **Write the head hash down outside the database** (in the register and somewhere the database
     owner cannot edit). A later check against that value shows whether the whole chain was
     rebuilt.
2. **Never run `scripts/simulate_tamper.py` during an incident.** It disables the append-only
   trigger and edits a row to test the check; on a live system it destroys evidence.
3. **Take a database snapshot** before changing anything: a Supabase backup or a `pg_dump` of the
   affected tables, stored encrypted and access-limited. Note where it is in the register.
4. **Keep the logs** of the backend, the agent and the listener for the period in question.
5. **Query, do not change.** Useful read-only sources:
   - `audit_log`: who did what and when (`action`, `detail`, `user_id`, `created_at`).
   - `model_egress`: what was sent to which model provider, per message (purpose, provider,
     character count, SHA-256 of the prompt, counts of hidden details); no text is stored. It does
     not cover document indexing or the listener's attachment reading
     ([`../known-issues.md`](../known-issues.md)).
   - `messages.masking_status`: rows still `pending` were quarantined because masking could not
     finish.

## 3. Contain

Pick the steps that match what was exposed.

**A user's Gmail access is at risk.** The user can revoke AIMail at
myaccount.google.com > Security > Third-party access. This stops access without deleting anything
in AIMail, so it is the first choice while evidence is still needed. `DELETE /account/gmail`
(Settings > Account > Disconnect) also revokes the token at Google, but then erases everything
stored from that mailbox (`Subject.MAILBOX` in `backend/app/erasure.py`); use it only after step 2.

**The shared API token is exposed.** Set a new `BACKEND_API_TOKEN` and restart the backend. Every
script and test that uses it needs the new value. It is server-side only and must never be in a
`VITE_` variable; if it was, the built dashboard bundle exposed it.

**The agent token is exposed.** Set a new `AGENT_TOKEN` for the backend and the Lane C agent and
restart both. The agent must stay bound to `127.0.0.1`.

**An encryption key is exposed.** Two keyrings protect stored secrets:
`TOKEN_ENCRYPTION_KEYS` (Gmail refresh tokens) and `PII_VAULT_KEYS` (each email's vault of hidden
details); the single-key settings `TOKEN_ENCRYPTION_KEY` and `PII_VAULT_KEY` are read as kid
`legacy`. Rotate as `backend/scripts/reseal_secrets.py` describes:
1. Put the new key first in the keyring and keep the old one in it.
2. Deploy the backend and the listener (both read these keys).
3. From `backend/`: `../.venv/bin/python scripts/reseal_secrets.py` (dry run, counts only), then
   with `--apply`.
4. Remove the old key.

Rotation protects data from now on. **It does not protect a copy already taken**: a dump stolen
together with the old key can still be opened. For a vault key, also consider emptying vaults early
(the retention job does this after `VAULT_RETENTION_DAYS`, default 30, or 7 days after the reply
was sent).

**Other credentials.** Replace `SUPABASE_SERVICE_KEY` (used by the listener, account deletion and `scripts/admin_accounts.py`),
`GOOGLE_API_KEY`, the Google OAuth client secret and the database password in their own consoles,
then update the settings of every service that reads them.

**Unmasked content was stored.** Quarantine or repair the rows: `backend/scripts/remask_outliers.py`
re-runs Presidio on candidates; re-upload documents to replace their chunks.

## 4. Assess

Work out, and write in the register:

- what kinds of data (masked text, vault contents, raw sender addresses, tokens);
- whose data, and how many people (count rows by `user_id`, never by reading content);
- whether the data was encrypted (vault and tokens are sealed; masked text is not encrypted at the
  application level);
- whether text left for Google Gemini (check `model_egress` for the messages involved);
- the likely harm to each group of people.

## 5. Notify

1. Tell the supervisor and the university's data protection contact with what is known.
2. With them, decide on notifying the Commissioner and affected individuals (see the legal duty
   above). Record each notification in the register: who, when, how, what was said.
3. Tell affected people in plain words what happened, what data, what has been done and what they
   can do (for example, revoke Google access or delete their AIMail account).

## 6. Erase where needed, then recover

1. If a person asks for deletion, or data must not be kept: `DELETE /account` (Settings > Account >
   Delete account) erases everything the user has (`Subject.ACCOUNT`), revokes the Gmail token and
   deletes the Supabase sign-in. The erasure registry in `backend/app/erasure.py` lists every table
   with a `user_id` as either erased or retained, and `backend/tests/test_erasure.py` fails if a new
   owned table is in neither list. `audit_log` is retained on purpose: its rows keep an opaque user
   id and, since 2026-10-08, structured fields with no address or body; older rows are free text.
   Erasure matches rows by `user_id`, so unowned rows (`user_id` NULL) from the original mailbox are
   not erased by deleting that owner's account unless they were handed over on connect.
2. **Backups.** The repository configures no backups; they are whatever the Supabase project
   provides. Check the Supabase project settings for what exists and how long it is kept. Erasure
   does not reach backups: after any restore, run the erasures again for every account deleted
   since the backup was taken.

## 7. Close

1. Fill in root cause and fix (with the PR number) in the register.
2. Add a regression test where the cause was in code.
3. Run the chain check again and compare the head hash with the one recorded in step 2.
4. Close the register entry with the date and who closed it.
