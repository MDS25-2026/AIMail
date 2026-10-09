"""FastAPI routes for natural language inbox search and thread Q&A assistant (Issue #144)."""

import logging

from fastapi import APIRouter, Depends, Request

from app.core.auth import require_mailbox, scope_of
from app.core.ratelimit import rate_limit_generation
from app.egress_log import save_egress
from app.inbox_search import (
    InboxSearchRequest,
    InboxSearchResponse,
    execute_inbox_search,
)
from app.private_mode import provider_for
from model_gateway import track_egress

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search")


@router.post(
    "/inbox",
    response_model=InboxSearchResponse,
    dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)],
)
async def inbox_search_endpoint(request: InboxSearchRequest, http: Request) -> InboxSearchResponse:
    """Natural language search and Q&A over masked emails and policy documents."""
    scope = scope_of(http)
    provider = await provider_for(scope.owner_id)

    with track_egress() as sent:
        response = await execute_inbox_search(request, scope=scope, provider=provider)

    await save_egress(sent, user_id=scope.owner_id, message_id=None)
    return response
