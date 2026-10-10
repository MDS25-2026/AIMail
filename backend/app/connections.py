"""Each user's connected Gmail (specs/features/per-user-mailboxes.md, step 2).

At sign-in Google returns a refresh token for the scopes the user actually granted. If Gmail read
access is among them, the token is sealed (app/core/token_crypt.py) and stored for that user. None
of this may block sign-in: a user without a connection simply sees "No mailbox connected".
"""

import logging
from uuid import UUID

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mailbox, token_crypt, vault
from app.core.supabase_auth import Session
from app.db.models import (
    Document,
    MailboxConnection,
    Message,
    ScheduledSend,
    SentMessage,
    UserProfile,
)
from app.db.session import get_sessionmaker

logger = logging.getLogger(__name__)

GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_SCOPES = (GMAIL_READ, GMAIL_SEND)
_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_TIMEOUT_SECONDS = 10.0


class ConnectionStoreError(RuntimeError):
    """The connection could not be checked or stored; the reason is in the message, never a token."""


async def granted_scopes(provider_token: str) -> set[str]:
    """The scopes Google actually granted, which may be fewer than were asked for."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(_TOKENINFO_URL, params={"access_token": provider_token})
            response.raise_for_status()
            return set(response.json().get("scope", "").split())
    except (httpx.HTTPError, ValueError) as exc:
        raise ConnectionStoreError(f"could not read the granted scopes: {exc}") from exc


async def _upsert_profile(session: AsyncSession, user_id: str, email: str, display_name: str) -> None:
    """The profile shares the auth user id, so messages.user_id and the personalisation tables (all
    keyed on user_profile) line up with the signed-in user. A name the user set is never replaced."""
    statement = insert(UserProfile).values(id=user_id, email=email.lower(), display_name=display_name or None)
    await session.execute(statement.on_conflict_do_update(
        index_elements=["id"],
        set_={"display_name": func.coalesce(UserProfile.display_name, statement.excluded.display_name)},
    ))


async def store_connection(
    user_id: str, email: str, refresh_token: str, scopes: list[str], display_name: str
) -> None:
    """Create the user's profile if new, then store or replace their sealed Gmail connection."""
    try:
        sealed = token_crypt.seal(refresh_token, user_id)
    except token_crypt.TokenKeyError as exc:
        raise ConnectionStoreError(str(exc)) from exc
    try:
        async with get_sessionmaker()() as session, session.begin():
            await _upsert_profile(session, user_id, email, display_name)
            values = {"email": email.lower(), "refresh_token_encrypted": sealed, "scopes": scopes,
                      "needs_reconnect": False}
            await session.execute(insert(MailboxConnection).values(user_id=user_id, **values)
                                  .on_conflict_do_update(index_elements=["user_id"],
                                                         set_={**values, "updated_at": func.now()}))
            if email.lower() == mailbox.owner():
                await _hand_over_unowned_rows(session, user_id)
    except (SQLAlchemyError, OSError) as exc:
        raise ConnectionStoreError(f"database refused the connection: {type(exc).__name__}") from exc


async def needs_reconnect(user_id: UUID) -> bool:
    async with get_sessionmaker()() as session:
        return bool(await session.scalar(select(MailboxConnection.needs_reconnect)
                                         .where(MailboxConnection.user_id == user_id)))


async def can_send(user_id: UUID) -> bool:
    """Whether the user granted Gmail send; Google lets people grant reading alone."""
    async with get_sessionmaker()() as session:
        scopes = await session.scalar(select(MailboxConnection.scopes)
                                      .where(MailboxConnection.user_id == user_id))
    return GMAIL_SEND in (scopes or [])


async def _reseal_unowned_vaults(session: AsyncSession, user_id: str) -> None:
    """Vaults are sealed against their owner, so rows changing owner need theirs sealed again. One
    that will not open (no key, corrupt) is left as it was: its details were unreadable anyway."""
    rows = (await session.execute(
        select(Message.id, Message.gmail_message_id, Message.pii_vault)
        .where(Message.user_id.is_(None), Message.pii_vault.is_not(None))
    )).all()
    for message_id, gmail_message_id, sealed in rows:
        try:
            resealed = vault.reseal_for_owner(sealed, gmail_message_id or "", None, UUID(user_id))
        except vault.VaultUnavailableError as exc:
            logger.warning("vault of message %s not moved to its owner: %s", message_id, exc)
            continue
        await session.execute(update(Message).where(Message.id == message_id).values(pii_vault=resealed))


async def _hand_over_unowned_rows(session: AsyncSession, user_id: str) -> None:
    """The original mailbox's account just connected: its unowned mail and documents become its own."""
    await _reseal_unowned_vaults(session, user_id)
    # Quiet hours stay: their row with no user is the company default, not the mailbox's.
    for model in (Message, Document, SentMessage, ScheduledSend):
        await session.execute(update(model).where(model.user_id.is_(None)).values(user_id=user_id))
    logger.info("handed the original mailbox's unowned rows over to user %s", user_id)


async def connect_mailbox(session: Session) -> None:
    """Store the Gmail connection a sign-in granted, if any. Logs and returns on every failure."""
    if not session.provider_refresh_token or not session.provider_token:
        logger.warning("Google sign-in returned no Google refresh token; Supabase sent fields: %s",
                       ", ".join(session.fields))
        return
    try:
        scopes = await granted_scopes(session.provider_token)
        if GMAIL_READ not in scopes:
            logger.info("user %s signed in without granting Gmail read access", session.user_id)
            return
        granted = sorted(scope for scope in scopes if scope in GMAIL_SCOPES)
        await store_connection(session.user_id, session.email, session.provider_refresh_token, granted,
                               session.full_name)
    except ConnectionStoreError as exc:
        logger.warning("could not store the Gmail connection for user %s: %s", session.user_id, exc)
        return
    logger.info("Gmail connected for user %s", session.user_id)
