# Personal data breach register

A record of every personal data breach, and every suspected breach that was investigated, in
AIMail. The steps for handling one are in [`breach-runbook.md`](breach-runbook.md).

## When an entry is required

Add an entry for any event where personal data AIMail holds was, or may have been, accessed,
disclosed, altered, lost or destroyed without authorisation. That includes:

- unmasked personal data reaching a place it should not (for example, a name or IC number found in
  `messages.body_masked`, a stored document, or text sent to Gemini);
- a key, token or credential exposed: `BACKEND_API_TOKEN`, `TOKEN_ENCRYPTION_KEY(S)`,
  `PII_VAULT_KEY(S)`, `AGENT_TOKEN`, `SUPABASE_SERVICE_KEY`, `GOOGLE_API_KEY`, the Google OAuth client
  secret, a user's Gmail refresh token, or the database URL;
- a reply sent to the wrong recipient, or a draft containing another person's details;
- the audit chain check failing (`GET /audit` returns `isChainIntact: false`, or
  `scripts/verify_audit_chain.py` exits 1);
- a lost or stolen device holding a database dump, `.env`, `listener/token.json` or exported data;
- data lost or destroyed by mistake (for example, a wrong erasure or a failed restore).

Record a suspected breach even if it turns out not to be one: write "not a breach" in the root
cause column with the reason. Never write a secret value, an email body or a person's details into
this file; describe the kind of data and refer to row ids.

## Columns

| Column | What to write |
|--------|---------------|
| Date found | When someone first noticed it (date and time, Malaysian time). |
| Date occurred | When it happened, or the earliest possible date if unknown. |
| What data | The kinds of personal data involved (names, email addresses, IC numbers, email content, vault contents, tokens), and the tables or files. |
| How many people | Number of people whose data was involved, or a range if not yet known. |
| How found | Who or what found it: a user report, the audit chain check, a log, a test. |
| Containment | What was done to stop it and when (token revoked, key rotated, row repaired, service stopped). |
| Who was told and when | The supervisor, the university, the Commissioner, affected people: each with the date and how. |
| Root cause | Why it happened, once known. |
| Fix | The change that stops it recurring, with the PR number. |
| Closed | Date closed and who closed it. |

## Register

| Date found | Date occurred | What data | How many people | How found | Containment | Who was told and when | Root cause | Fix | Closed |
|------------|---------------|-----------|-----------------|-----------|-------------|-----------------------|------------|-----|--------|
| | | | | | | | | | |
