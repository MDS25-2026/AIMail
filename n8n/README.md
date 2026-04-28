# n8n

n8n workflows for AImail, exported as JSON and version-controlled here. Two primary workflows:

1. **Inbound** — Gmail trigger → webhook to listener.
2. **Outbound** — Backend calls n8n → n8n sends the approved reply via Gmail.

## Run locally

_Not built yet._ Placeholder steps:

```bash
# Run n8n locally (docker)
docker run -it --rm -p 5678:5678 -v ~/.n8n:/home/node/.n8n n8nio/n8n
# Then import the JSON workflows from this folder via the n8n UI.
```

## Key dependencies

- n8n (self-hosted; version pinned in `specs/context/tech-stack.md`)
- Gmail OAuth credentials (configured inside n8n, not committed)

## Env vars / credentials

Stored inside n8n itself, never committed. Required:

- Gmail OAuth (per-user)
- `LISTENER_URL` (HTTP request node target)
- `LISTENER_SHARED_SECRET` (header on webhook call)

## Folder structure

```
n8n/
├── inbound-gmail-watch.json    # exported workflow (TODO)
├── outbound-send-reply.json    # exported workflow (TODO)
└── README.md
```

Re-export workflows after every change. Don't hand-edit the JSON.
