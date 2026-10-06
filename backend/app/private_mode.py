"""Private mode (specs/features/local-model.md): a user's choice to keep their email in the company.

The company offers it by setting LOCAL_LLM_MODEL; each user then chooses it in Settings. The stored
choice is honoured even if the company later removes the model: drafts then fail and are retried,
rather than quietly going to Gemini against the user's choice.
"""

from enum import StrEnum
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import UserPreferences
from app.db.session import get_sessionmaker


class DraftProvider(StrEnum):
    GEMINI = "gemini"
    LOCAL = "local"


def is_offered() -> bool:
    return bool(get_settings().local_llm_model.strip())


async def provider_for(user_id: UUID | None) -> DraftProvider:
    """Rows with no owner (the original mailbox) always use Gemini: nobody chose otherwise."""
    if user_id is None:
        return DraftProvider.GEMINI
    async with get_sessionmaker()() as session:
        chosen = await session.scalar(select(UserPreferences.draft_provider)
                                      .where(UserPreferences.user_id == user_id))
    return DraftProvider(chosen or DraftProvider.GEMINI)
