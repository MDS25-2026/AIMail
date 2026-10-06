# listener (Lane A)

Go service that watches every connected Gmail inbox, masks PII, and persists each message to
Supabase. Each user who signs in with Google has a `mailbox_connection` row holding their refresh
token, sealed by the backend (`tokencrypt.go` reads it). The listener sets up a Gmail `watch` per
mailbox on one shared Pub/Sub topic, routes each notification by its `emailAddress`, masks PII, and
writes the masked row (tagged with the owner's `user_id`) plus an audit entry via PostgREST. New
sign-ups are picked up every two minutes without a restart; each mailbox's history baseline is
saved on its connection row, so a restart resumes where it stopped.

The original `token.json` mailbox still runs, storing rows with no owner, until its account signs
in with Google; then its connection replaces it. Pub/Sub itself still authenticates as the
`token.json` account for now (a service account replaces that before `token.json` retires).

Masking is split by PII nature. Format-clear PII (email, phone, Malaysian IC) is redacted by an
ordered, offline regex floor — most-specific first, and a bare 12-digit run is only typed as an IC
when its `YYMMDD` prefix is a plausible date, so numbers aren't mis-typed by length. Context-dependent
PII (names, locations, organizations, account numbers) is then found by Microsoft Presidio's analyzer
(a local container). If Presidio is unreachable the message is quarantined with no content until it
can be masked.

Every detail becomes a numbered placeholder (`[PERSON_1]`, `[PHONE_2]`), the same value always the
same number within an email, and the placeholder-to-value map is sealed with `PII_VAULT_KEY` into
the row's `pii_vault` (`details.go`), so the backend can show the owner the real details and fill
them into an approved reply while the AI only ever sees placeholders
(`specs/features/restorable-masking.md`). Replacement happens in this service, so the Presidio
anonymizer container is no longer used.

## Run locally

Needs, in this folder, `credentials.json` and `token.json` (OAuth for the shared Gmail and
Pub/Sub), and in the repo-root `.env`: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and for connected
users `TOKEN_ENCRYPTION_KEY`, `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` (the same values
as the backend).

```bash
docker compose up -d   # from repo root: starts Presidio analyzer :5001 + anonymizer :5002 (optional)
cd listener
go run .        # first run opens a browser to log in as the shared Gmail, then writes token.json
```

Expect `ingesting the mailbox of user ...` for each connected user, then `Listening for incoming
emails on Pub/Sub...`. Send a mail to
the watched inbox to see it masked and stored. Re-auth by deleting `token.json` and re-running.

## Config

- `ProjectID`, `TopicName`, `SubscriptionID` — constants at the top of `main.go` (the GCP project +
  Pub/Sub topic/subscription).
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — read from the repo-root `.env` (loaded via godotenv).
- `TOKEN_ENCRYPTION_KEY` — unseals stored refresh tokens; must match the backend's.
- `PII_VAULT_KEY` — seals each email's detail vault; must match the backend's. Without it, emails
  are still masked but their details cannot be shown or restored.
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` — the web client in Supabase's Google
  provider; a connected user's token can only be refreshed with the client that issued it.
- `PRESIDIO_ANALYZER_URL`, `PRESIDIO_ANONYMIZER_URL` — Presidio endpoints; default to `localhost:5001/5002`
  (the `docker-compose.yml` services). Optional — unset/unreachable degrades to regex-only masking.
- `credentials.json` — OAuth client downloaded from Google Cloud (gitignored).
- `token.json` — OAuth token, written on consent and rewritten on refresh (gitignored).

## Key dependencies

- Go 1.22+
- `google.golang.org/api/gmail`, `cloud.google.com/go/pubsub`, `golang.org/x/oauth2`
- `github.com/joho/godotenv`

## Files

```
listener/
├── main.go                 # watch, Pub/Sub loop, layered PII masking, Supabase writes
├── mailboxes.go            # connected mailboxes: load, watch, route by address, per-mailbox baseline
├── tokencrypt.go           # AES-GCM shared with the backend: refresh tokens, detail vaults
├── details.go              # numbered placeholders and the sealed per-email detail vault
├── main_test.go            # offline regex-floor tests: typing, ordering, IC date gate, false-positive guards
├── presidio_live_test.go   # live NER tests against the containers; self-skip when Presidio is down
├── credentials.json        # OAuth client (gitignored)
└── token.json              # OAuth token (gitignored, regenerated on re-auth)
```

Presidio containers are defined in the repo-root `docker-compose.yml`.
