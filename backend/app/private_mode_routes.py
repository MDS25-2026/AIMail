"""Settings > Private mode. Per signed-in user only."""

from enum import StrEnum

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert

from app.account_routes import account_user_id
from app.audit import audit
from app.core.config import get_settings
from app.db.models import UserPreferences
from app.db.session import get_sessionmaker
from app.private_mode import DraftProvider, is_offered, provider_for

router = APIRouter()


class PrivateModeError(StrEnum):
    UNAVAILABLE = "private_mode_unavailable"


class PrivateModeView(BaseModel):
    available: bool
    enabled: bool
    model: str


class PrivateModeBody(BaseModel):
    enabled: bool


async def _view(request: Request) -> PrivateModeView:
    provider = await provider_for(account_user_id(request))
    return PrivateModeView(available=is_offered(), enabled=provider == DraftProvider.LOCAL,
                           model=get_settings().local_llm_model)


@router.get("/settings/private-mode")
async def get_private_mode(request: Request) -> PrivateModeView:
    return await _view(request)


@router.put("/settings/private-mode")
async def put_private_mode(body: PrivateModeBody, request: Request) -> PrivateModeView:
    user_id = account_user_id(request)
    # Switching off is always allowed: it must never be stuck on a model the company removed.
    if body.enabled and not is_offered():
        raise HTTPException(status.HTTP_409_CONFLICT, PrivateModeError.UNAVAILABLE)
    provider = DraftProvider.LOCAL if body.enabled else DraftProvider.GEMINI
    statement = insert(UserPreferences).values(user_id=user_id, draft_provider=provider)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(statement.on_conflict_do_update(
            index_elements=["user_id"], set_={"draft_provider": provider, "updated_at": func.now()}))
    await audit("private_mode", f"user={user_id} enabled={body.enabled}")
    return await _view(request)
