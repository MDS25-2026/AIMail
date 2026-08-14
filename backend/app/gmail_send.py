"""Send an approved reply via the Gmail API.

Reuses the listener's OAuth token (it already holds the gmail.send scope), refreshing the access
token on demand. Best-practice upgrade: a Workspace service account with domain-wide delegation, so
the backend authenticates as itself instead of borrowing the listener's token.
"""

import base64
import json
from email.message import EmailMessage
from pathlib import Path

import httpx

from app.core.config import get_settings

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class SendError(RuntimeError):
    """Sending the reply via Gmail failed."""


def _load_creds() -> tuple[dict, dict]:
    settings = get_settings()
    installed = json.loads(Path(settings.gmail_credentials_path).read_text())["installed"]
    token = json.loads(Path(settings.gmail_token_path).read_text())
    return installed, token


async def _access_token(client: httpx.AsyncClient) -> str:
    installed, token = _load_creds()
    resp = await client.post(
        _TOKEN_URL,
        data={
            "client_id": installed["client_id"],
            "client_secret": installed["client_secret"],
            "refresh_token": token["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _build_raw(to_addr: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to_addr
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


async def send_reply(to_addr: str, subject: str, body: str) -> None:
    raw = _build_raw(to_addr, subject, body)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            access_token = await _access_token(client)
            resp = await client.post(
                _SEND_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"raw": raw},
            )
            resp.raise_for_status()
    except (httpx.HTTPError, KeyError, OSError, json.JSONDecodeError) as exc:
        raise SendError(str(exc)) from exc
