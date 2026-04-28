# listener

Tiny HTTP service that receives the n8n webhook on new email and forwards the payload to the backend. Kept deliberately small so it can be re-implemented in Go later for performance benchmarking.

Initial implementation: Python (FastAPI or Flask — TBD). Go rewrite tracked under a separate spec.

## Run locally

_Not built yet._ Placeholder steps:

```bash
cd listener
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # TODO
uvicorn app:app --reload --port 8001   # TODO
```

## Key dependencies

- Python 3.11+ (initial) / Go 1.22+ (later)
- FastAPI or Flask (Python)
- httpx for forwarding

## Env vars

Defined in `.env.example` (TODO):

- `BACKEND_URL`
- `LISTENER_SHARED_SECRET` (must match backend)
- `N8N_WEBHOOK_TOKEN`

## Folder structure

```
listener/
├── app.py             # entrypoint (Python, TODO)
├── go/                # Go reimplementation (later)
└── requirements.txt
```
