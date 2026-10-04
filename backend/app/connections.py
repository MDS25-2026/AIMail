"""Each user's connected Gmail (specs/features/per-user-mailboxes.md, step 2).

At sign-in Google returns a refresh token for the scopes the user actually granted. If Gmail read
access is among them, the token is sealed (app/core/token_crypt.py) and stored for that user. None
of this may block sign-in: a user without a connection simply sees "No mailbox connected".
"""

import logging

import httpx
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.core import token_crypt
from app.core.supabase_auth import Session
from app.db.models import MailboxConnection, UserProfile
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


async def store_connection(user_id: str, email: str, refresh_token: str, scopes: list[str]) -> None:
    """Create the user's profile if new, then store or replace their sealed Gmail connection."""
    try:
        sealed = token_crypt.seal(refresh_token, user_id)
    except token_crypt.TokenKeyError as exc:
        raise ConnectionStoreError(str(exc)) from exc
    try:
        async with get_sessionmaker()() as session, session.begin():
            # The profile shares the auth user id, so messages.user_id and the personalisation
            # tables (all keyed on user_profile) line up with the signed-in user.
            await session.execute(insert(UserProfile).values(id=user_id, email=email.lower())
                                  .on_conflict_do_nothing(index_elements=["id"]))
            values = {"email": email.lower(), "refresh_token_encrypted": sealed, "scopes": scopes}
            await session.execute(insert(MailboxConnection).values(user_id=user_id, **values)
                                  .on_conflict_do_update(index_elements=["user_id"],
                                                         set_={**values, "updated_at": func.now()}))
    except (SQLAlchemyError, OSError) as exc:
        raise ConnectionStoreError(f"database refused the connection: {type(exc).__name__}") from exc


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
        await store_connection(session.user_id, session.email, session.provider_refresh_token, granted)
    except ConnectionStoreError as exc:
        logger.warning("could not store the Gmail connection for user %s: %s", session.user_id, exc)
        return
    logger.info("Gmail connected for user %s", session.user_id)
