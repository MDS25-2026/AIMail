# Backbone contracts (2026-10-08)

The shared shapes the backbone work builds on. Every service follows these; change them here first.

## Sender verification: `messages.auth_status`

| Value | Written by | Meaning | Drafting | Holding reply |
|---|---|---|---|---|
| `pass` | listener | Google's own Authentication-Results says DMARC (or SPF and DKIM) passed | yes | yes |
| `spoof_detected` | listener | SPF, DKIM or DMARC failed | no, until confirmed | no |
| `unverified` | listener, and the column default | no verdict: no header from Google's server, `none`, `temperror`, `permerror` | yes, with a notice | no |
| `sender_confirmed` | backend | the owner checked a `spoof_detected` sender | yes | no |

Only the topmost `Authentication-Results` header whose authserv-id is `mx.google.com` counts; a header the
sender added is ignored. Unknown always reads as unverified, never as pass.

## Audit rows: `audit_log`

- `action`: a value of the shared action list (backend `AuditAction`, listener constants).
- `detail`: a JSON object, compact, keys sorted (`json.dumps(fields, sort_keys=True, separators=(",", ":"))`),
  e.g. `{"gmail_message_id":"18f...","reason":"masking did not complete"}`. Never prose, never an email address or
  body text. Rows written before 2026-10-08 hold prose; readers show them as text.
- `user_id`: the owner the action was for, also from the listener. No foreign key: the id stays, opaque, after
  the account is deleted, so the hash chain never changes under it.
- Rows are append-only: the database refuses UPDATE and DELETE on `audit_log`.

## Errors from the backend

Every error response is `{"error": {"code": "<code>", "message": "<English, for logs>"}}`, with the HTTP status from
one table. Codes come from one registry (`app/core/errors.py`, `ErrorCode`). The dashboard maps codes to i18n keys
and never shows `message`.

## `GET /audit` (camelCase, like every other endpoint)

`{isChainIntact, totalRecords, verifiedRecords, headHash, events: [{id, createdAt, action, fields, success,
prevHash, currentHash, verification}]}`, where `fields` is the parsed `detail` object (or `{"text": "<prose>"}` for
old rows) and `verification` is `verified` | `tampered` | `unverifiable`.

## What an email may do

One policy decides it: backend `refusal_for(message, action)`, dashboard `draftAvailability(email)`. The email
response carries `authStatus` and `masking`; the dashboard derives availability from them with the same rules:
quarantined (`masking` pending or abandoned) shows no draft; `spoof_detected` shows the sender check; otherwise ready.

## Reaching a model: `model_gateway`

Every prompt and every embedding goes through `backend/model_gateway.py` (`generate`, `embed_documents`,
`embed_query`), in the backend and the agent. The provider is a required argument; agent requests without
`provider` are refused (422). The gateway runs the fixed-format floor over the whole prompt as a last net, sends
system rules as the system message, and records each prompt as an egress record (purpose, provider, chars,
sha256, hidden details by kind, details caught by the last net). The backend keeps them in `model_egress`
(migration 0026); the email detail response returns them as `egress` for the privacy receipt. Switching
Private mode on deletes the user's Gemini vectors; `/search` and `/ask` use the user's provider.
