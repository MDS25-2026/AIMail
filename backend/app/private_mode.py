"""Private mode (specs/features/local-model.md): a user's choice to keep their email in the company.

The company offers it by setting LOCAL_LLM_MODEL; each user then chooses it in Settings. The stored
choice is honoured even if the company later removes the model: drafts then fail and are retried,
rather than quietly going to Gemini against the user's choice.
"""

from uuid import UUID

from sqlalchemy import ColumnElement, or_, select

from app.core.config import get_settings
from app.core.errors import DomainError, ErrorCode
from app.core.providers import Provider
from app.db.models import UserPreferences
from app.db.session import get_sessionmaker


def is_offered() -> bool:
    return bool(get_settings().local_llm_model.strip())


async def provider_for(user_id: UUID | None) -> Provider:
    """Rows with no owner (the original mailbox) always use Gemini: nobody chose otherwise."""
    if user_id is None:
        return Provider.GEMINI
    async with get_sessionmaker()() as session:
        chosen = await session.scalar(select(UserPreferences.draft_provider)
                                      .where(UserPreferences.user_id == user_id))
    return Provider(chosen or Provider.GEMINI)


async def model_for(user_id: UUID | None) -> Provider:
    """The provider a model call for this owner uses. Private mode on a server with no private model is
    refused, never quietly sent to Gemini instead: that would break the promise the setting makes."""
    provider = await provider_for(user_id)
    if provider == Provider.LOCAL and not is_offered():
        raise DomainError(ErrorCode.PRIVATE_MODEL_UNAVAILABLE)
    return provider


def not_private(user_column: ColumnElement) -> ColumnElement[bool]:
    """Rows not owned by a Private mode user: theirs never go to Gemini, as text or as vectors."""
    private_users = select(UserPreferences.user_id).where(UserPreferences.draft_provider == Provider.LOCAL)
    return or_(user_column.is_(None), user_column.not_in(private_users))
