# AIMail privacy notice

> **Draft, not legal advice. Review before publishing.** This draft describes what the code does
> as of 2026-10-11. It has not been reviewed by the university or a legal adviser, and the contact
> details are placeholders.

AIMail helps you answer work email. It reads the email in the Gmail account you connect, hides
personal details before any text is sent to an AI model, writes reply drafts, and sends nothing
until you approve it.

## What AIMail keeps

**Your account.** Your name and email address from Google sign-in, your role and responsibilities if
you enter them, and your settings (writing
style, saved replies, quiet hours, rules, Private mode and other preferences).

**Your Gmail connection.** A Google refresh token so AIMail can read and send mail for you. It is
stored encrypted.

**Your email, masked.** For each email: the subject, the body and a short preview, with personal
details replaced by placeholders such as `[PERSON_1]` or `[PHONE_1]`. Names, email addresses, phone
numbers, Malaysian IC numbers, card numbers and some account numbers are hidden. Some details are
not hidden: company names, street numbers, and account numbers with nothing around them to show
what they are. The sender's email address is kept as it is, because AIMail needs it to send your
reply. AIMail also keeps the draft it wrote, a summary, action items, a priority and a category.

**The hidden details, locked.** The real values behind the placeholders are kept in an encrypted
vault for each email, so the dashboard can show them to you and fill them into your reply when it
is sent. They are never sent to an AI model.

**Replies you send.** A masked copy of each reply you send, so AIMail can show which ones are still
waiting for an answer. If you switch on "Learn from the replies I send", AIMail also keeps the
draft it showed you next to what you sent, to learn your style.

**Documents you add.** Policies or other documents you upload as background for replies. They are
masked before they are stored.

**Audit records.** A log of actions such as drafting, refining, sending, disconnecting and deleting.
It records what happened and when, with an internal user id; it holds no email content. It cannot
be edited or deleted, so tampering can be detected.

**Egress records.** For each prompt sent to an AI model: what it was for, which model provider,
how many characters, a fingerprint (SHA-256) of the text, and how many details were hidden. The
text itself is not kept. These records are what the "Privacy receipt" in the dashboard shows.

## What goes to Google Gemini

By default AIMail uses Google Gemini to read, summarise and draft replies. **Only masked text is
sent**: the email and earlier messages in the thread with placeholders in place of personal
details, matching passages from your documents (also masked), and your writing style. The vault
of real details is never sent.

Exceptions you should know about:

- **Scanned attachments.** By default a scan is read on AIMail's own machine and its image is not
  sent to Gemini. If you choose "checked" scans, a local model first looks for signatures, faces
  and stamps, and only an image where it finds none is sent to Gemini, with the text it could read
  redacted. The local check misses about 1 in 10 signatures, faces and stamps, and text the local
  reader could not see is not redacted.
- **What you type yourself.** When you refine a draft, edit it, search or ask a question, AIMail
  hides fixed-format details (email addresses, phone numbers, IC numbers, card numbers) and puts
  details it already knows back into placeholders, but a name you type that it has not seen before
  is sent as you typed it.
- **Search.** To find matching passages, the masked text of your documents and emails is turned
  into numbers (embeddings) by Gemini, unless you use Private mode.

Google's handling of data sent to Gemini is governed by Google's terms for the API, not by AIMail.

## Private mode

If your organisation runs its own model, you can switch on Private mode in Settings. Your drafts,
summaries, refines, translations and searches then use that model on your organisation's machine,
instead of Gemini. Masking still applies. Limits:

- documents and emails already sent to Gemini for search before you switched stay sent;
- if your account still uses mail stored before you connected your own Gmail, Private mode is not
  applied to that mail until you connect.

## How long AIMail keeps things

A daily job removes data on these schedules:

| Data | Kept for |
|------|----------|
| Vault of hidden details | 30 days after the email arrived, or 7 days after your reply was sent, whichever comes first |
| Draft-and-sent pairs kept for learning | 90 days after sending |
| Masked copies of replies you sent | 90 days |
| Recipients of automatic holding replies | 60 days |
| Finished or cancelled "send later" items | 30 days |
| Egress records | 365 days |
| Rate-limit counters | 1 day |
| Masked email content (body, preview, summary, draft) | Until your organisation sets a limit; by default it is kept |
| Past replies and style examples kept for learning your style | Until you disconnect Gmail or delete your account |
| Audit records | Kept; they hold no email content |

If a limit is set for email content, the copies of sent replies and finished "send later" items are
removed at that limit too, if it is shorter.

## Deleting your data

- **Disconnect Gmail** (Settings > Account): AIMail stops reading your mailbox, revokes its access
  at Google, and deletes everything it stored from that mailbox: emails, sent replies, holding
  replies, egress records, and what it learned from your sends.
- **Delete your account** (Settings > Account): everything above, plus your documents, writing
  style, saved replies, settings and your sign-in.
- **Audit records stay** after deletion. They keep an internal id that no longer links to an
  account, and no email content.
- **Mail stored before you connected your own Gmail.** If your account is the owner of the original
  shared mailbox and you never connected Gmail, that mail is not yet linked to your account and is
  not removed by account deletion. Ask the contact below to remove it.
- **Backups.** Deleted data can remain in database backups until those backups expire.
- You can also remove AIMail's access yourself in your Google account, under Security >
  Third-party access. That stops access but does not delete what AIMail already stored.

## For reviewers

Not part of the notice. Sources for each statement, as of 2026-10-11:

- Retention: `backend/app/retention.py` and `backend/app/vault_retention.py`, run daily by
  `backend/app/worker.py`. `VAULT_RETENTION_DAYS` defaults to 30; `MESSAGE_CONTENT_RETENTION_DAYS`
  defaults to 0 (kept). No policy expires `document` rows of type sent reply or `style_example`
  rows taken from sends; erasure removes them.
- Erasure: `backend/app/erasure.py` (`RULES`, `RETAINED`), called by `backend/app/account.py`.
  It matches rows by `user_id`, so unowned rows (`user_id` NULL) are not erased until they are
  handed over on connect (`backend/app/connections.py`).
- Typed text: `details.for_model` in `backend/app/dashboard.py` (refine) and `mask_typed_text`
  (`/search`, `/ask`, inbox search).
- Audit rows: since 2026-10-08 they hold structured fields with no address or body
  (`listener/audit.go`); rows written before that date are free text and were not reviewed for
  personal content.
- Private mode: `specs/features/local-model.md`; its acceptance test that no request reaches
  Gemini in Private mode is not yet ticked.

## Contact

Questions, requests to see or correct your data, or complaints:

- Data protection contact: `[NAME, ROLE]`
- Email: `[CONTACT EMAIL]`
- Organisation: `[ORGANISATION NAME AND ADDRESS]`

If you are not satisfied with the answer, you can complain to the Personal Data Protection
Commissioner of Malaysia.
