"""Send an approved reply via the Gmail API.

Reuses the listener's OAuth token (it already holds the gmail.send scope), refreshing the access
token on demand. Best-practice upgrade: a Workspace service account with domain-wide delegation, so
the backend authenticates as itself instead of borrowing the listener's token.
"""

import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_SEND_URL = f"{_MESSAGES_URL}/send"
# Read from Gmail at send time, never from the database: the stored subject is masked, and Gmail
# threads a reply only when its Subject matches the original's.
_ORIGINAL_HEADERS = ("Subject", "From", "Reply-To", "Message-ID", "References")
_REPLY_PREFIX = "re:"


@dataclass(frozen=True)
class ReplyTarget:
    """Where a reply goes and which thread it joins. Held in memory only, never stored or logged."""

    to_addr: str
    subject: str
    thread_id: str | None = None
    in_reply_to: str | None = None
    references: str | None = None


@dataclass(frozen=True)
class SentReply:
    gmail_id: str | None
    thread_id: str | None
    message_id: str | None


class SendError(RuntimeError):
    """Sending the reply via Gmail failed, before Gmail could have sent it."""


class SendOutcomeUnknownError(RuntimeError):
    """Gmail may have sent the reply but the answer was lost. Never retried: that risks a second copy."""


# Failures raised before a request can reach Gmail. Any other transport failure on the POST may
# have landed after Gmail accepted it.
_NEVER_REACHED_GMAIL = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


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


def _reply_subject(subject: str) -> str:
    return subject if subject.lower().startswith(_REPLY_PREFIX) else f"Re: {subject}"


def _reply_references(target: ReplyTarget) -> str:
    """The original's References plus its own Message-ID (RFC 5322 section 3.6.4)."""
    return " ".join(part for part in (target.references, target.in_reply_to) if part)


def _build_raw(target: ReplyTarget, body: str) -> str:
    text = _strip_subject_line(body)
    message = EmailMessage()
    message["To"] = target.to_addr
    message["Subject"] = _reply_subject(target.subject)
    if target.in_reply_to:
        message["In-Reply-To"] = target.in_reply_to
        message["References"] = _reply_references(target)
    # multipart/alternative: HTML for clients that render it, plain text for those that do not.
    message.set_content(text)
    message.add_alternative(_html_body(text), subtype="html")
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


async def _gmail_request(
    client: httpx.AsyncClient, method: str, url: str, **kwargs: object
) -> httpx.Response:
    global _cached_token
    for attempt in range(2):
        access_token = await _access_token(client)
        response = await client.request(
            method, url, headers={"Authorization": f"Bearer {access_token}"}, **kwargs
        )
        # A cached token can be revoked before it expires. Drop it and try once with a fresh
        # one, so a revocation costs one retry rather than every call until restart.
        if response.status_code != httpx.codes.UNAUTHORIZED or attempt:
            return response
        _cached_token = None
    return response


async def message_headers(
    client: httpx.AsyncClient, gmail_id: str, names: tuple[str, ...]
) -> dict:
    """The named headers of a message, keyed lower-case, plus its threadId. Headers only, no body."""
    response = await _gmail_request(
        client, "GET", f"{_MESSAGES_URL}/{gmail_id}",
        params=[("format", "metadata"), *(("metadataHeaders", name) for name in names)],
    )
    response.raise_for_status()
    payload = response.json()
    headers = {h["name"].lower(): h["value"] for h in payload.get("payload", {}).get("headers", [])}
    return headers | {"threadid": payload.get("threadId")}


# The stored subject is masked; with the original gone from Gmail it is all there is. A subject
# carrying a redaction marker would show "[Redacted]" to the recipient, so it is not used.
_MARKER = re.compile(r"\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]")
NEUTRAL_SUBJECT = "Your message"


def _sendable_subject(masked_subject: str) -> str:
    return NEUTRAL_SUBJECT if _MARKER.search(masked_subject) or not masked_subject.strip() else masked_subject


async def _reply_target(
    client: httpx.AsyncClient, gmail_id: str | None, fallback_to: str, fallback_subject: str
) -> ReplyTarget:
    """Thread identity and real subject from the original; standalone if it no longer exists."""
    fallback = ReplyTarget(to_addr=fallback_to, subject=_sendable_subject(fallback_subject))
    if not gmail_id:
        return fallback
    try:
        headers = await message_headers(client, gmail_id, _ORIGINAL_HEADERS)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == httpx.codes.NOT_FOUND:
            return fallback
        raise
    return ReplyTarget(
        to_addr=headers.get("reply-to") or headers.get("from") or fallback_to,
        subject=headers.get("subject") or fallback_subject,
        thread_id=headers.get("threadid"),
        in_reply_to=headers.get("message-id"),
        references=headers.get("references"),
    )


async def _sent_message_id(client: httpx.AsyncClient, gmail_id: str | None) -> str | None:
    """Read back the Message-ID Gmail actually gave our reply, rather than assuming ours survived.

    Never raises: the reply is already sent, and failing here would invite a second send.
    """
    if not gmail_id:
        return None
    try:
        return (await message_headers(client, gmail_id, ("Message-ID",))).get("message-id")
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("sent reply %s: could not read back its Message-ID: %s", gmail_id, exc)
        return None


async def _post_send(client: httpx.AsyncClient, payload: dict[str, str]) -> dict:
    """POST the reply. A failure Gmail may already have acted on raises SendOutcomeUnknownError."""
    try:
        response = await _gmail_request(client, "POST", _SEND_URL, json=payload)
    except httpx.TransportError as exc:
        if isinstance(exc, _NEVER_REACHED_GMAIL):
            raise
        raise SendOutcomeUnknownError(f"no answer from Gmail: {exc}") from exc
    response.raise_for_status()  # an error status means Gmail refused, so nothing was sent
    try:
        return response.json()
    except ValueError as exc:
        raise SendOutcomeUnknownError("Gmail accepted the send but its answer was unreadable") from exc


async def send_reply(
    gmail_message_id: str | None, fallback_to: str, fallback_subject: str, body: str
) -> SentReply:
    """Send `body` as a reply in the original's thread. The fallbacks serve only when the
    original is gone from Gmail or the row predates gmail_message_id."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            target = await _reply_target(client, gmail_message_id, fallback_to, fallback_subject)
            payload: dict[str, str] = {"raw": _build_raw(target, body)}
            if target.thread_id:
                payload["threadId"] = target.thread_id
            sent = await _post_send(client, payload)
            message_id = await _sent_message_id(client, sent.get("id"))
    except (httpx.HTTPError, KeyError, OSError, ValueError) as exc:
        raise SendError(str(exc)) from exc
    return SentReply(gmail_id=sent.get("id"), thread_id=sent.get("threadId"), message_id=message_id)
