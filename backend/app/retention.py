"""How long each kind of stored data is kept, in one table run by one daily job (PDPA retention).

The vault policy is the long-standing one (app/vault_retention.py). The others close the gaps the
2026-10-08 audit found: learning pairs, holding-reply recipients and egress records were kept forever, and
message content had no limit at all. Message content is kept until MESSAGE_CONTENT_RETENTION_DAYS is set,
because clearing it removes the user's own inbox view; the rest expire by default.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import Executable, delete, func, update

from app.core.config import get_settings
from app.db.models import (
    HoldingReply,
    Message,
    ModelEgress,
    RateLimitCounter,
    SentMessage,
)
from app.db.session import get_sessionmaker
from app.vault_retention import expired

logger = logging.getLogger(__name__)

# The learner reads only the last 20 sends; a quarter is ample.
LEARNING_PAIR_DAYS = 90
# Past the longest cooldown a holding reply can set (30 days), the address is not needed to space replies.
HOLDING_RECIPIENT_DAYS = 60
EGRESS_DAYS = 365
# Rate-limit windows last a minute or two; a day of history is plenty to look back on.
RATE_LIMIT_WINDOW_DAYS = 1
# A sent reply is kept only to see who has not answered; after a quarter that question is stale.
SENT_MESSAGE_DAYS = 90
KEEP_FOREVER = 0


@dataclass(frozen=True)
class Policy:
    name: str
    days: Callable[[], int]  # KEEP_FOREVER (0) switches the policy off
    statement: Callable[[int], Executable]


def _older_than(days: int):
    return func.now() - timedelta(days=days)


def _vault(days: int) -> Executable:
    return update(Message).where(expired(days)).values(pii_vault=None)


def _learning_pairs(days: int) -> Executable:
    return (update(Message).where(Message.draft_shown.is_not(None), Message.sent_at < _older_than(days))
            .values(draft_shown=None, edit_ratio=None))


def _holding_recipients(days: int) -> Executable:
    return (update(HoldingReply).where(HoldingReply.recipient_addr != "", HoldingReply.created_at < _older_than(days))
            .values(recipient_addr=""))


def _egress(days: int) -> Executable:
    return delete(ModelEgress).where(ModelEgress.created_at < _older_than(days))


def _rate_limit_windows(days: int) -> Executable:
    return delete(RateLimitCounter).where(RateLimitCounter.window_start < _older_than(days))


def _message_content(days: int) -> Executable:
    # Counts, priority, thread identity and the audit trail stay; the readable content goes.
    return (update(Message).where(Message.created_at < _older_than(days), Message.body_masked != "")
            .values(body_masked="", snippet_masked="", ai_summary="", draft_reply="", rag_sources=None,
                    action_items=None))


def _sent_messages(days: int) -> Executable:
    return delete(SentMessage).where(SentMessage.sent_at < _older_than(days))


POLICIES: tuple[Policy, ...] = (
    Policy("vault", lambda: get_settings().vault_retention_days, _vault),
    Policy("learning_pairs", lambda: LEARNING_PAIR_DAYS, _learning_pairs),
    Policy("holding_reply_recipients", lambda: HOLDING_RECIPIENT_DAYS, _holding_recipients),
    Policy("model_egress", lambda: EGRESS_DAYS, _egress),
    Policy("rate_limit_windows", lambda: RATE_LIMIT_WINDOW_DAYS, _rate_limit_windows),
    Policy("message_content", lambda: get_settings().message_content_retention_days, _message_content),
    Policy("sent_messages", lambda: SENT_MESSAGE_DAYS, _sent_messages),
)


async def apply_retention() -> dict[str, int]:
    """Rows changed per policy; each policy commits on its own so one failure does not undo the rest."""
    changed: dict[str, int] = {}
    for policy in POLICIES:
        days = policy.days()
        if days == KEEP_FOREVER:
            continue
        async with get_sessionmaker()() as session, session.begin():
            result = await session.execute(policy.statement(days))
        changed[policy.name] = result.rowcount or 0
    return changed
