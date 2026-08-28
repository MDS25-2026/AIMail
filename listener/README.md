# listener (Lane A)

Go service that watches a Gmail inbox, masks PII, and persists each message to Supabase. It sets up
a Gmail `watch` that pushes to a Pub/Sub topic, pulls each new message, masks PII, and writes the
masked row plus an audit entry via Supabase's PostgREST API.

Masking is split by PII nature. Format-clear PII (email, phone, Malaysian IC) is redacted by an
ordered, offline regex floor — most-specific first, and a bare 12-digit run is only typed as an IC
when its `YYMMDD` prefix is a plausible date, so numbers aren't mis-typed by length. Context-dependent
PII (names, locations, organizations, account numbers) is then handled by Microsoft Presidio NER (two
local containers). If Presidio is unreachable the service degrades to the regex floor — raw text is
never stored — and notes `presidio degraded` on the audit row.

## Run locally

Needs, in this folder, `credentials.json` and `token.json` (OAuth for the shared Gmail), and
`SUPABASE_URL` + `SUPABASE_SERVICE_KEY` in the repo-root `.env`.

```bash
docker compose up -d   # from repo root: starts Presidio analyzer :5001 + anonymizer :5002 (optional)
cd listener
go run .        # first run opens a browser to log in as the shared Gmail, then writes token.json
```

Expect `Gmail Watch established!` then `Listening for incoming emails on Pub/Sub...`. Send a mail to
the watched inbox to see it masked and stored. Re-auth by deleting `token.json` and re-running.

## Config

- `ProjectID`, `TopicName`, `SubscriptionID` — constants at the top of `main.go` (the GCP project +
  Pub/Sub topic/subscription).
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` — read from the repo-root `.env` (loaded via godotenv).
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
├── main.go            # the whole service: watch, Pub/Sub loop, layered PII masking, Supabase writes
├── main_test.go       # verifies the regex floor holds when Presidio is down
├── credentials.json   # OAuth client (gitignored)
└── token.json         # OAuth token (gitignored, regenerated on re-auth)
```

Presidio containers are defined in the repo-root `docker-compose.yml`.
