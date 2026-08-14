"""Minimal webhook listener: receive a new-mail event, forward it to the backend.

Scaffold only (Lane A owns this service). Provider-agnostic — works whether the event
source is n8n or Google Pub/Sub. Auth and the real forward contract are placeholders;
confirm the /ingest shape with the backend (Seam 1) before relying on this.
"""

import os

import httpx
from fastapi import FastAPI, Header, HTTPException, status
from pydantic import BaseModel

app = FastAPI(title="AImail listener")

# Endpoints/secrets come from the environment, never hardcoded. See .env.example.
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
SHARED_SECRET = os.environ.get("LISTENER_SHARED_SECRET", "")


class MailEvent(BaseModel):
    gmail_message_id: str
    thread_id: str


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook(event: MailEvent, x_listener_secret: str = Header(default="")) -> dict[str, str]:
    if SHARED_SECRET and x_listener_secret != SHARED_SECRET:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid shared secret")
    async with httpx.AsyncClient() as client:
        await client.post(f"{BACKEND_URL}/ingest", json=event.model_dump())
    return {"forwarded": event.gmail_message_id}
