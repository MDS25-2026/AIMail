# listener (Lane A)

Go service that watches every connected Gmail inbox, masks PII, and persists each message to
Supabase. Each user who signs in with Google has a `mailbox_connection` row holding their refresh
token, sealed by the backend (`tokencrypt.go` reads it). The listener sets up a Gmail `watch` per
mailbox on one shared Pub/Sub topic, routes each notification by its `emailAddress`, masks PII, and
writes the masked row (tagged with the owner's `user_id`) plus an audit entry via PostgREST. New
sign-ups are picked up every two minutes without a restart; each mailbox's history baseline is
saved on its connection row, so a restart resumes where it stopped.

The original `token.json` mailbox still runs, storing rows with no owner, until its account signs
in with Google; then its connection replaces it. It is optional: without `credentials.json`, or
without `token.json` and no terminal to sign in on, it is skipped and the service runs on connected
mailboxes alone. Pub/Sub authenticates as the `token.json` account while there is one, otherwise
with Application Default Credentials (a deployment's service account).

Masking is split by PII nature. Format-clear PII (email, phone, Malaysian IC) is redacted by an
ordered, offline regex floor — most-specific first, and a bare 12-digit run is only typed as an IC
when its `YYMMDD` prefix is a plausible date, so numbers aren't mis-typed by length. Context-dependent
PII (names, locations, organizations, account numbers, Malaysian postcodes and car plates) is then
found by Microsoft Presidio's analyzer (a local container); account numbers, postcodes and plates only
count when a nearby word (bank, jalan, plate...) says what they are. If Presidio is unreachable the
message is quarantined with no content until it can be masked.

Before masking, every text part of the body is read and converted from the sender's charset to UTF-8,
HTML is reduced to prose, and Gmail's HTML-escaped snippet is unescaped. Attachments are read by the
type their bytes show, not the type the sender declared; ones of a type the reader cannot handle are
counted in the audit log. If Gmail no longer has the history since the last notification (a listener
down for over a week), the 50 newest inbox messages are checked and the ones not yet stored are ingested.

Every detail becomes a numbered placeholder (`[PERSON_1]`, `[PHONE_2]`), the same value always the
same number within an email, and the placeholder-to-value map is sealed with `PII_VAULT_KEY` into
the row's `pii_vault` (`details.go`), so the backend can show the owner the real details and fill
them into an approved reply while the AI only ever sees placeholders
(`specs/features/restorable-masking.md`). Replacement happens in this service, so the Presidio
anonymizer container is no longer used.

## Run locally

Needs, in this folder, `credentials.json` and `token.json` (OAuth for the shared Gmail and
Pub/Sub), and in the repo-root `.env`: `GCP_PROJECT_ID`, `PUBSUB_TOPIC`, `PUBSUB_SUBSCRIPTION`,
`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and for connected
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
Ctrl+C or SIGTERM stops it cleanly.

## Run as a service

`docker build -t aimail-listener listener/` builds a static binary on a distroless, non-root image.
Pass the settings below as environment variables and give the container a service account for
Pub/Sub; no `credentials.json` or `token.json` goes into the image. Probe `GET :8095/healthz`
(process up) and `GET :8095/readyz` (503 while Supabase or Presidio is unreachable; also reports
`seconds_since_last_receive`, which is informational because a quiet inbox is normal).

## Config

- `GCP_PROJECT_ID`, `PUBSUB_TOPIC` (the short topic id), `PUBSUB_SUBSCRIPTION` — required, no
  defaults; the listener exits at startup naming whichever is missing.
- `LISTENER_HEALTH_ADDR` — where `/healthz` and `/readyz` are served; default `127.0.0.1:8095`.
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — read from the repo-root `.env` (loaded via godotenv).
- `TOKEN_ENCRYPTION_KEYS` / `PII_VAULT_KEYS` — keyrings for rotation, `kid:base64key,kid2:base64key`
  with the first entry primary; must match the backend's. New vaults are sealed in format 2 under the
  primary key, and any listed key still opens what it sealed. The single keys below are kid `legacy`.
- `TOKEN_ENCRYPTION_KEY` — unseals stored refresh tokens; must match the backend's.
- `PII_VAULT_KEY` — seals each email's detail vault; must match the backend's. Without it, emails
  are still masked but their details cannot be shown or restored.
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` — the web client in Supabase's Google
  provider; a connected user's token can only be refreshed with the client that issued it.
- `PRESIDIO_ANALYZER_URL`, `PRESIDIO_ANONYMIZER_URL` — Presidio endpoints; default to `localhost:5001/5002`
  (the `docker-compose.yml` services). Optional — unset/unreachable degrades to regex-only masking.
- `credentials.json` — OAuth client downloaded from Google Cloud (gitignored).
- `token.json` — OAuth token, written on consent (gitignored).

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
├── authresults.go          # sender verdict from Google's own Authentication-Results header
├── sender.go               # sender facts computed once for every messages row
├── audit.go                # audit rows: action constants, sorted-JSON detail, owner id
├── privatemode.go          # the owner's Private mode choice, read before any image goes to OCR
├── config.go, health.go    # Pub/Sub settings from the environment; /healthz and /readyz
├── legacy_token.go         # the optional token.json mailbox
├── Dockerfile              # distroless, non-root service image
├── details.go              # numbered placeholders and the sealed per-email detail vault
├── main_test.go            # offline regex-floor tests: typing, ordering, IC date gate, false-positive guards
├── presidio_live_test.go   # live NER tests against the containers; self-skip when Presidio is down
├── credentials.json        # OAuth client (gitignored)
└── token.json              # OAuth token (gitignored, regenerated on re-auth)
```

Presidio containers are defined in the repo-root `docker-compose.yml`.
