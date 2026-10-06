"""Whose mailbox the stored emails belong to (ADR 0005, stage 1).

The listener reads one mailbox, and the backend holds that account's Gmail login to send replies,
so the owner is read from Gmail at startup rather than typed into .env. MAILBOX_OWNER_EMAIL is only
a fallback for when Gmail cannot be reached. Stage 2 replaces this with an owner per stored email.
"""

import logging

import httpx

from app.core.config import get_settings
from app.gmail_send import profile_address as gmail_address

logger = logging.getLogger(__name__)

_detected = ""


async def resolve_owner() -> None:
    """Ask Gmail once whose mailbox this is. A failure keeps the fallback rather than crashing."""
    global _detected
    try:
        _detected = (await gmail_address()).strip().lower()
    # Network, an unexpected reply shape, unreadable JSON, or no Gmail token file on this machine.
    except (httpx.HTTPError, KeyError, ValueError, OSError) as exc:
        logger.warning("could not read the Gmail address of the connected mailbox: %s", exc)
        return
    logger.info("connected mailbox owner resolved from Gmail")


def owner() -> str:
    """The mailbox owner's address, lower-case, or "" when neither Gmail nor the setting says."""
    return _detected or get_settings().mailbox_owner_email.strip().lower()
