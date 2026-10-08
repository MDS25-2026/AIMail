"""Disconnecting Gmail and deleting an account (specs/features/per-user-mailboxes.md, step 5).

Disconnect stops AIMail reading a mailbox and deletes what it stored from it; deleting the account
also removes the user's knowledge base, settings and sign-in account (the PDPA right to erasure).
Every step can be repeated safely, so a failure part-way is finished by trying again.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy import select

from app.audit import AuditAction, audit
from app.core import token_crypt
from app.core.config import get_settings
from app.db.models import Document, MailboxConnection, Message
from app.db.session import get_sessionmaker
from app.erasure import Subject, erase

logger = logging.getLogger(__name__)

_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
_TIMEOUT_SECONDS = 10.0
# Supabase answers 404 for a user already deleted, which is the outcome we want.
_ALREADY_GONE = 404


class NotConnectedError(RuntimeError):
    """The user has no connected Gmail to disconnect."""


class AccountDeletionError(RuntimeError):
    """A step failed; what is deleted stays deleted, and trying again finishes the rest."""


@dataclass(frozen=True)
class Erased:
    messages: int
    documents: int = 0


async def _revoke_at_google(user_id: UUID, sealed: bytes) -> None:
    """Best effort: the user's data is deleted either way, and they can revoke in their Google account."""
    try:
        token = token_crypt.unseal(sealed, str(user_id))
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(_REVOKE_URL, data={"token": token})
        if not response.is_success:
            logger.warning("Google did not revoke the token of user %s: status %d", user_id, response.status_code)
    except (token_crypt.TokenKeyError, token_crypt.TokenDecryptError, httpx.HTTPError) as exc:
        logger.warning("could not revoke the token of user %s at Google: %s", user_id, exc)


async def disconnect_gmail(user_id: UUID) -> Erased:
    async with get_sessionmaker()() as session:
        sealed = await session.scalar(select(MailboxConnection.refresh_token_encrypted)
                                      .where(MailboxConnection.user_id == user_id))
    if sealed is None:
        raise NotConnectedError(str(user_id))
    await _revoke_at_google(user_id, sealed)
    async with get_sessionmaker()() as session, session.begin():
        counts = await erase(session, user_id, Subject.MAILBOX)
    erased = Erased(messages=counts.get(Message.__tablename__, 0), documents=counts.get(Document.__tablename__, 0))
    await audit(AuditAction.DISCONNECT_GMAIL, user_id=user_id, messages_deleted=erased.messages)
    return erased


async def _delete_sign_in(user_id: UUID) -> None:
    settings = get_settings()
    if not (settings.supabase_url and settings.supabase_service_key):
        raise AccountDeletionError("SUPABASE_URL and SUPABASE_SERVICE_KEY are needed to delete the sign-in")
    headers = {"apikey": settings.supabase_service_key, "Authorization": f"Bearer {settings.supabase_service_key}"}
    url = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.delete(url, headers=headers)
    except httpx.HTTPError as exc:
        raise AccountDeletionError(f"Supabase unreachable: {exc}") from exc
    if not (response.is_success or response.status_code == _ALREADY_GONE):
        raise AccountDeletionError(f"Supabase refused to delete the sign-in: status {response.status_code}")


async def delete_account(user_id: UUID) -> Erased:
    """Everything the user has in AIMail, then the sign-in itself, which comes last so a failure
    leaves an empty account they can delete again rather than data nobody can reach."""
    try:
        await disconnect_gmail(user_id)
    except NotConnectedError:
        pass  # nothing connected: there is no token to revoke
    async with get_sessionmaker()() as session, session.begin():
        counts = await erase(session, user_id, Subject.ACCOUNT)
    await _delete_sign_in(user_id)
    erased = Erased(messages=counts.get(Message.__tablename__, 0), documents=counts.get(Document.__tablename__, 0))
    await audit(AuditAction.DELETE_ACCOUNT, user_id=user_id, documents_deleted=erased.documents)
    return erased
