"""Send an approved reply via the Gmail API.

Reuses the listener's OAuth token (it already holds the gmail.send scope), refreshing the access
token on demand. Best-practice upgrade: a Workspace service account with domain-wide delegation, so
the backend authenticates as itself instead of borrowing the listener's token.
"""

import base64
import json
import re
import time
from email.message import EmailMessage
from html import escape
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


# Access tokens last about an hour, so refreshing on every send added a second round trip to
# Google before the mail could go out — the whole of the delay between clicking Approve & Send and
# the reply appearing. Cached until shortly before expiry. A concurrent send may refresh twice,
# which is harmless and cheaper than serialising every send behind a lock.
_cached_token: tuple[str, float] | None = None
_EXPIRY_MARGIN_SECONDS = 60


async def _access_token(client: httpx.AsyncClient) -> str:
    global _cached_token
    now = time.monotonic()
    if _cached_token is not None and _cached_token[1] > now:
        return _cached_token[0]

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
    payload = resp.json()
    access_token = payload["access_token"]
    lifetime = float(payload.get("expires_in", 3600))
    _cached_token = (access_token, now + lifetime - _EXPIRY_MARGIN_SECONDS)
    return access_token


_SUBJECT_LINE = re.compile(r"^\s*subject\s*:.*(?:\r?\n)+", re.IGNORECASE)


def _strip_subject_line(body: str) -> str:
    """Drop a leading "Subject: ..." the generator wrote into the draft.

    The subject is set as a header below, so leaving it in the body sends it twice — once
    where it belongs and once as the first visible line of the reply.
    """
    return _SUBJECT_LINE.sub("", body, count=1).lstrip()


def _html_body(body: str) -> str:
    """Render the draft as paragraphs so the reader's client reflows it.

    Sent as text/plain, the draft is folded at 78 characters to satisfy RFC 2045 and every
    client then renders that fixed width literally — a narrow ragged column however wide the
    window. Paragraphs let the client decide the measure, which is what real mail does.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "".join(
        # Single newlines inside a paragraph are wrapping, not intent; <br> keeps deliberate
        # breaks like a signature block.
        f"<p>{'<br>'.join(escape(line) for line in p.splitlines())}</p>"
        for p in paragraphs
    )


def _build_raw(to_addr: str, subject: str, body: str) -> str:
    text = _strip_subject_line(body)
    message = EmailMessage()
    message["To"] = to_addr
    message["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    # multipart/alternative: HTML for clients that render it, plain text for those that do not.
    message.set_content(text)
    message.add_alternative(_html_body(text), subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


async def _post_message(client: httpx.AsyncClient, raw: str) -> httpx.Response:
    access_token = await _access_token(client)
    return await client.post(
        _SEND_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw},
    )


async def send_reply(to_addr: str, subject: str, body: str) -> None:
    global _cached_token
    raw = _build_raw(to_addr, subject, body)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await _post_message(client, raw)
            if resp.status_code == httpx.codes.UNAUTHORIZED:
                # A cached token can be revoked before it expires. Drop it and try once with a
                # fresh one, so a revocation costs one retry rather than every send until restart.
                _cached_token = None
                resp = await _post_message(client, raw)
            resp.raise_for_status()
    except (httpx.HTTPError, KeyError, OSError, json.JSONDecodeError) as exc:
        raise SendError(str(exc)) from exc
