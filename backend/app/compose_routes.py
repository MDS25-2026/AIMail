"""Compose's routes (specs/features/compose.md). The signed-in user's own drafts only; another's read as missing."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.account_routes import account_user_id
from app.agent_contract import Tone
from app.compose import (
    MAX_ADDRESS_CHARS,
    MAX_BRIEF_CHARS,
    MAX_RECIPIENTS,
    MAX_SUBJECT_CHARS,
    ComposeFields,
    SettleOutcome,
    create_draft,
    delete_draft,
    get_draft,
    list_drafts,
    refine,
    send,
    settle,
    update_draft,
    write,
)
from app.contracts import ComposeDraftView, ComposeList
from app.core.auth import require_mailbox
from app.core.constants import MAX_DRAFT_CHARS, MAX_INSTRUCTION_CHARS
from app.core.ratelimit import (
    rate_limit_detail,
    rate_limit_generation,
    rate_limit_list,
    rate_limit_send,
)

router = APIRouter(prefix="/compose")

Address = Annotated[str, Field(max_length=MAX_ADDRESS_CHARS)]


class DraftBody(BaseModel):
    """Any field the user typed; one left out keeps what is stored."""

    to: list[Address] | None = Field(default=None, max_length=MAX_RECIPIENTS)
    cc: list[Address] | None = Field(default=None, max_length=MAX_RECIPIENTS)
    subject: str | None = Field(default=None, max_length=MAX_SUBJECT_CHARS)
    brief: str | None = Field(default=None, max_length=MAX_BRIEF_CHARS)
    body: str | None = Field(default=None, max_length=MAX_DRAFT_CHARS)
    tone: Tone | None = None

    def fields(self) -> ComposeFields:
        return ComposeFields(to=self.to, cc=self.cc, subject=self.subject, brief=self.brief, body=self.body,
                             tone=self.tone)


class RefineBody(DraftBody):
    instruction: str = Field(min_length=1, max_length=MAX_INSTRUCTION_CHARS)  # "shorter", "mention the deadline"


class SendBody(BaseModel):
    """The email exactly as approved: every field is sent, none is read back from storage instead."""

    to: list[Address] = Field(min_length=1, max_length=MAX_RECIPIENTS)
    cc: list[Address] = Field(default_factory=list, max_length=MAX_RECIPIENTS)
    subject: str = Field(min_length=1, max_length=MAX_SUBJECT_CHARS)
    body: str = Field(min_length=1, max_length=MAX_DRAFT_CHARS)
    # Remind me if they don't reply, whatever the reply says; unticked, the rules decide.
    remindIfNoReply: bool = False

    def fields(self) -> ComposeFields:
        return ComposeFields(to=self.to, cc=self.cc, subject=self.subject, body=self.body)


class OutcomeBody(BaseModel):
    outcome: SettleOutcome


@router.get("", dependencies=[Depends(rate_limit_list)])
async def list_route(request: Request) -> ComposeList:
    return await list_drafts(account_user_id(request))


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_mailbox)])
async def create_route(body: DraftBody, request: Request) -> ComposeDraftView:
    return await create_draft(account_user_id(request), body.fields())


@router.get("/{draft_id}", dependencies=[Depends(rate_limit_detail)])
async def get_route(draft_id: UUID, request: Request) -> ComposeDraftView:
    return await get_draft(account_user_id(request), draft_id)


@router.patch("/{draft_id}", dependencies=[Depends(require_mailbox)])
async def update_route(draft_id: UUID, body: DraftBody, request: Request) -> ComposeDraftView:
    return await update_draft(account_user_id(request), draft_id, body.fields())


@router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_mailbox)])
async def delete_route(draft_id: UUID, request: Request) -> Response:
    await delete_draft(account_user_id(request), draft_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{draft_id}/write", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def write_route(draft_id: UUID, body: DraftBody, request: Request) -> ComposeDraftView:
    return await write(account_user_id(request), draft_id, body.fields())


@router.post("/{draft_id}/refine", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def refine_route(draft_id: UUID, body: RefineBody, request: Request) -> ComposeDraftView:
    return await refine(account_user_id(request), draft_id, body.instruction, body.fields())


@router.post("/{draft_id}/send", dependencies=[Depends(rate_limit_send), Depends(require_mailbox)])
async def send_route(draft_id: UUID, body: SendBody, request: Request) -> ComposeDraftView:
    return await send(account_user_id(request), draft_id, body.fields(),
                      remind=True if body.remindIfNoReply else None)


@router.post("/{draft_id}/outcome", dependencies=[Depends(require_mailbox)])
async def outcome_route(draft_id: UUID, body: OutcomeBody, request: Request) -> ComposeDraftView:
    return await settle(account_user_id(request), draft_id, body.outcome)
