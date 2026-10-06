"""Per-user policy applied on top of the classifier's prediction.

The classifier stays text-only and untouched, so its macro-F1 against the human holdout remains
comparable across every change here. Personalisation happens strictly afterwards, which also means
it works with one user today: a rule needs no training data, whereas a per-user model needs
corrections we do not have.

Precedence, most specific first:

1. a sender rule for that exact address
2. a keyword rule matching the subject or body
3. the model's prediction, shifted by the user's bias
4. medium, when the classifier has not scored the message yet

The bias is deliberately three-valued. It is derived from a handful of calibration judgements, and
anything finer would be fitting noise — see docs/backlog.md item 1.

Nothing here is ever interpolated into a prompt. Sender and keyword rules are lookups; only the
profile text reaches the model, and only for drafting.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KeywordRule, Message, SenderRule, UserPreferences, UserProfile

_LOW, _MEDIUM, _HIGH = 0, 1, 2
_LABELS = {_LOW: "low", _MEDIUM: "medium", _HIGH: "high"}


@dataclass(frozen=True)
class Policy:
    """A user's resolved preferences. The default instance reproduces current behaviour exactly."""

    priority_bias: int = 0
    default_sort: str = "date"
    default_tone: str = "professional"
    sender_rules: dict[str, int] = field(default_factory=dict)
    keyword_rules: dict[str, int] = field(default_factory=dict)
    profile_text: str = ""


DEFAULT_POLICY = Policy()


async def load_policy(session: AsyncSession, email: str) -> Policy:
    """Read one user's policy. Returns the neutral default when they have configured nothing."""
    profile = (
        await session.execute(select(UserProfile).where(UserProfile.email == email.lower()))
    ).scalars().first()
    if profile is None:
        return DEFAULT_POLICY

    prefs = (
        await session.execute(
            select(UserPreferences).where(UserPreferences.user_id == profile.id)
        )
    ).scalars().first()
    senders = (
        await session.execute(select(SenderRule).where(SenderRule.user_id == profile.id))
    ).scalars().all()
    keywords = (
        await session.execute(select(KeywordRule).where(KeywordRule.user_id == profile.id))
    ).scalars().all()

    return Policy(
        priority_bias=prefs.priority_bias if prefs else 0,
        default_sort=prefs.default_sort if prefs else "date",
        default_tone=prefs.default_tone if prefs else "professional",
        sender_rules={r.from_addr.lower(): r.priority for r in senders},
        keyword_rules={r.keyword.lower(): r.priority for r in keywords},
        profile_text=_profile_text(profile),
    )


def _profile_text(profile: UserProfile) -> str:
    """The one piece of personalisation that reaches a model, and only for drafting."""
    parts = [p for p in (profile.display_name, profile.role, profile.responsibilities) if p]
    return " — ".join(parts)


def apply_policy(message: Message, policy: Policy) -> str:
    """Resolve the priority a given user should see for a message."""
    sender = (message.from_addr or "").lower()
    for addr, priority in policy.sender_rules.items():
        # Substring rather than equality: a From header is "Name <addr>", not a bare address.
        if addr and addr in sender:
            return _LABELS[priority]

    haystack = f"{message.subject or ''}\n{message.body_masked or ''}".lower()
    for keyword, priority in policy.keyword_rules.items():
        if keyword and keyword in haystack:
            return _LABELS[priority]

    if message.importance is None:
        return _LABELS[_MEDIUM]  # unscored: the placeholder, unchanged by bias

    shifted = min(_HIGH, max(_LOW, message.importance + policy.priority_bias))
    return _LABELS[shifted]
