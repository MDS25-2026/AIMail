"""Send an approved reply via the Gmail API, from the mailbox the email arrived in.

A connected user's mailbox uses their own refresh token, stored sealed in mailbox_connection and
refreshed with the Google OAuth client that issued it (GOOGLE_OAUTH_CLIENT_ID/SECRET). Rows with no
owner belong to the original single mailbox, which still uses the listener's token.json.
"""

import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select, update

from app.core import token_crypt
from app.core.config import get_settings
from app.core.draft_text import strip_subject_line
from app.core.errors import DomainError, ErrorCode
from app.db.models import MailboxConnection
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://oauth2.googleapis.com/token"
INVALID_GRANT = "invalid_grant"
_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
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


class _CodedSendError(DomainError):
    """A send failure the API answers with its code only; the reason (which can name local paths) is logged."""

    code_for_class = ErrorCode.SEND_FAILED

    def __init__(self, reason: str = "") -> None:
        super().__init__(self.code_for_class)
        self.reason = reason

    def __str__(self) -> str:
        return self.reason or self.code.value


class SendError(_CodedSendError):
    """Sending the reply via Gmail failed, before Gmail could have sent it."""


class GmailAccessError(RuntimeError):
    """No usable Google credentials for this mailbox. The reason never includes a token."""


class GoogleAccessExpiredError(GmailAccessError):
    """Google refused the user's refresh token (invalid_grant): only signing in again fixes it."""


class AccessExpiredSendError(SendError):
    """The send failed because the user's Google access has ended."""

    code_for_class = ErrorCode.GOOGLE_ACCESS_EXPIRED


class SendOutcomeUnknownError(_CodedSendError):
    """Gmail may have sent the reply but the answer was lost. Never retried: that risks a second copy."""

    code_for_class = ErrorCode.SEND_OUTCOME_UNKNOWN


# Failures raised before a request can reach Gmail. Any other transport failure on the POST may
# have landed after Gmail accepted it.
_NEVER_REACHED_GMAIL = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


def _load_creds() -> tuple[dict, dict]:
    settings = get_settings()
    installed = json.loads(Path(settings.gmail_credentials_path).read_text())["installed"]
    token = json.loads(Path(settings.gmail_token_path).read_text())
    return installed, token


async def _connection_grant(owner_id: UUID) -> dict[str, str]:
    """A connected user's refresh token, with the OAuth client it was issued to."""
    settings = get_settings()
    if not (settings.google_oauth_client_id and settings.google_oauth_client_secret):
        raise GmailAccessError("GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET are required")
    async with get_sessionmaker()() as session:
        sealed = await session.scalar(select(MailboxConnection.refresh_token_encrypted)
                                      .where(MailboxConnection.user_id == owner_id))
    if sealed is None:
        raise GmailAccessError(f"user {owner_id} has no connected Gmail")
    try:
        refresh_token = token_crypt.unseal(sealed, str(owner_id))
    except (token_crypt.TokenKeyError, token_crypt.TokenDecryptError) as exc:
        raise GmailAccessError(f"stored token for user {owner_id} is unreadable: {exc}") from exc
    return {"client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret, "refresh_token": refresh_token}


async def _refresh_grant(owner_id: UUID | None) -> dict[str, str]:
    """What to refresh with: a user's own connection, or token.json for the original mailbox."""
    if owner_id is not None:
        return await _connection_grant(owner_id)
    installed, token = _load_creds()
    return {"client_id": installed["client_id"], "client_secret": installed["client_secret"],
            "refresh_token": token["refresh_token"]}


# Access tokens last about an hour, so refreshing on every send added a second round trip to
# Google before the mail could go out — the whole of the delay between clicking Approve & Send and
# the reply appearing. Cached per mailbox (None is the original one) until shortly before expiry.
# A concurrent send may refresh twice, which is harmless and cheaper than a lock.
_cached_tokens: dict[UUID | None, tuple[str, float]] = {}
_EXPIRY_MARGIN_SECONDS = 60


async def _mark_needs_reconnect(owner_id: UUID) -> None:
    """The dashboard then asks the user to sign in again (specs/features/per-user-mailboxes.md)."""
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(update(MailboxConnection).where(MailboxConnection.user_id == owner_id)
                              .values(needs_reconnect=True))
    logger.warning("google refused the token of user %s; marked to reconnect", owner_id)


def _is_refused_grant(response: httpx.Response) -> bool:
    """Testing-mode tokens expire after 7 days, and revoked ones look the same."""
    if response.status_code != httpx.codes.BAD_REQUEST:
        return False
    try:
        return response.json().get("error") == INVALID_GRANT
    except ValueError:
        return False


async def _access_token(client: httpx.AsyncClient, owner_id: UUID | None) -> str:
    now = time.monotonic()
    cached = _cached_tokens.get(owner_id)
    if cached is not None and cached[1] > now:
        return cached[0]
    resp = await client.post(
        _TOKEN_URL, data={**await _refresh_grant(owner_id), "grant_type": "refresh_token"}
    )
    if owner_id is not None and _is_refused_grant(resp):
        await _mark_needs_reconnect(owner_id)
        raise GoogleAccessExpiredError(f"google refused the token of user {owner_id}")
    resp.raise_for_status()
    payload = resp.json()
    access_token = payload["access_token"]
    lifetime = float(payload.get("expires_in", 3600))
    _cached_tokens[owner_id] = (access_token, now + lifetime - _EXPIRY_MARGIN_SECONDS)
    return access_token


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


def _build_raw(target: ReplyTarget, body: str, extra_headers: dict[str, str] | None = None) -> str:
    # The agent strips it now; drafts stored before that still carry it.
    text = strip_subject_line(body)
    message = EmailMessage()
    for name, value in (extra_headers or {}).items():
        message[name] = value
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
    client: httpx.AsyncClient, method: str, url: str, owner_id: UUID | None, **kwargs: object
) -> httpx.Response:
    for attempt in range(2):
        access_token = await _access_token(client, owner_id)
        response = await client.request(
            method, url, headers={"Authorization": f"Bearer {access_token}"}, **kwargs
        )
        # A cached token can be revoked before it expires. Drop it and try once with a fresh
        # one, so a revocation costs one retry rather than every call until restart.
        if response.status_code != httpx.codes.UNAUTHORIZED or attempt:
            return response
        _cached_tokens.pop(owner_id, None)
    return response


async def message_headers(
    client: httpx.AsyncClient, gmail_id: str, names: tuple[str, ...], owner_id: UUID | None
) -> dict:
    """The named headers of a message, keyed lower-case, plus its threadId. Headers only, no body."""
    response = await _gmail_request(
        client, "GET", f"{_MESSAGES_URL}/{gmail_id}", owner_id,
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
    client: httpx.AsyncClient, gmail_id: str | None, fallback_to: str, fallback_subject: str,
    owner_id: UUID | None,
) -> ReplyTarget:
    """Thread identity and real subject from the original; standalone if it no longer exists."""
    fallback = ReplyTarget(to_addr=fallback_to, subject=_sendable_subject(fallback_subject))
    if not gmail_id:
        return fallback
    try:
        headers = await message_headers(client, gmail_id, _ORIGINAL_HEADERS, owner_id)
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


async def _sent_message_id(
    client: httpx.AsyncClient, gmail_id: str | None, owner_id: UUID | None
) -> str | None:
    """Read back the Message-ID Gmail actually gave our reply, rather than assuming ours survived.

    Never raises: the reply is already sent, and failing here would invite a second send.
    """
    if not gmail_id:
        return None
    try:
        return (await message_headers(client, gmail_id, ("Message-ID",), owner_id)).get("message-id")
    except (httpx.HTTPError, GmailAccessError, KeyError, ValueError) as exc:
        logger.warning("sent reply %s: could not read back its Message-ID: %s", gmail_id, exc)
        return None


_THREADS_URL = "https://gmail.googleapis.com/gmail/v1/users/me/threads"


async def has_written_to(address: str, *, owner_id: UUID) -> bool:
    """Whether the owner has ever sent mail to this address (holding reply "correspondents")."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await _gmail_request(client, "GET", _MESSAGES_URL, owner_id,
                                        params={"q": f"in:sent to:{address}", "maxResults": 1})
        response.raise_for_status()
        return bool(response.json().get("messages"))


async def replied_in_thread_since(thread_id: str, since: datetime, *, owner_id: UUID) -> bool:
    """Whether the owner sent anything in this Gmail thread after `since`, from Gmail or anywhere."""
    since_ms = int(since.timestamp() * 1000)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await _gmail_request(client, "GET", f"{_THREADS_URL}/{thread_id}", owner_id,
                                        params={"format": "minimal"})
        response.raise_for_status()
        messages = response.json().get("messages", [])
    return any("SENT" in m.get("labelIds", []) and int(m.get("internalDate", 0)) > since_ms
               for m in messages)


async def sent_message_in_thread_since(thread_id: str, since: datetime, *, owner_id: UUID | None) -> str | None:
    """The id of a message the owner sent in this thread after `since`, if Gmail has one: how a send whose
    answer was lost is confirmed or ruled out (app/send_reconciler.py)."""
    since_ms = int(since.timestamp() * 1000)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await _gmail_request(client, "GET", f"{_THREADS_URL}/{thread_id}", owner_id,
                                        params={"format": "minimal"})
        response.raise_for_status()
        messages = response.json().get("messages", [])
    sent = [m for m in messages if "SENT" in m.get("labelIds", []) and int(m.get("internalDate", 0)) > since_ms]
    return sent[0].get("id") if sent else None


async def profile_address() -> str:
    """The address of the original single mailbox (token.json), the owner of unowned rows."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await _gmail_request(client, "GET", _PROFILE_URL, None)
        response.raise_for_status()
        return response.json()["emailAddress"]


async def _post_send(
    client: httpx.AsyncClient, payload: dict[str, str], owner_id: UUID | None
) -> dict:
    """POST the reply. A failure Gmail may already have acted on raises SendOutcomeUnknownError."""
    try:
        response = await _gmail_request(client, "POST", _SEND_URL, owner_id, json=payload)
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
    gmail_message_id: str | None, fallback_to: str, fallback_subject: str, body: str,
    *, owner_id: UUID | None, extra_headers: dict[str, str] | None = None,
) -> SentReply:
    """Send `body` as a reply in the original's thread, from the owner's mailbox. The fallbacks
    serve only when the original is gone from Gmail or the row predates gmail_message_id."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            target = await _reply_target(client, gmail_message_id, fallback_to, fallback_subject,
                                         owner_id)
            payload: dict[str, str] = {"raw": _build_raw(target, body, extra_headers)}
            if target.thread_id:
                payload["threadId"] = target.thread_id
            sent = await _post_send(client, payload, owner_id)
            message_id = await _sent_message_id(client, sent.get("id"), owner_id)
    except GoogleAccessExpiredError as exc:
        raise AccessExpiredSendError(str(exc)) from exc
    except (httpx.HTTPError, GmailAccessError, KeyError, OSError, ValueError) as exc:
        raise SendError(str(exc)) from exc
    return SentReply(gmail_id=sent.get("id"), thread_id=sent.get("threadId"), message_id=message_id)
