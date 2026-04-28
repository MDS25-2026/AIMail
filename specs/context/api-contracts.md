# API contracts

This file is the **contract between frontend and backend**. Every REST endpoint AImail exposes is documented here. Frontend and backend must both match this file.

## Rules

- Add an endpoint here **before** writing it.
- Update this file in the same PR that changes a request/response shape.
- Keep examples short — link to the relevant feature spec for full detail.

## Conventions

- Base URL: `${NEXT_PUBLIC_BACKEND_URL}` (configurable per environment).
- All requests/responses are JSON.
- Auth: TBD (probably session cookie + CSRF).
- Errors follow this shape:

```json
{
  "error": {
    "code": "PII_MASKING_FAILED",
    "message": "Human-readable summary",
    "details": {}
  }
}
```

## Endpoints

> _None defined yet. Add endpoints below as feature specs land._

### TODO

- [ ] `POST /webhooks/email` — listener → backend ingress.
- [ ] `GET /threads` — list threads with most recent draft.
- [ ] `GET /threads/{id}` — full thread + draft.
- [ ] `POST /drafts/{id}/approve` — approve draft, trigger send.
- [ ] `POST /drafts/{id}/edit` — user edits before approval.
- [ ] `POST /drafts/{id}/reject` — discard draft.
