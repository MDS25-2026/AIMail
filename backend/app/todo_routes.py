"""To-do (specs/features/todo-page.md): what needs the reader, and the settings for it."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from app.account_routes import account_user_id
from app.audit import AuditAction, audit
from app.core import mailbox
from app.core.auth import principal_of, require_mailbox, scope_of
from app.core.constants import MAX_DRAFT_CHARS
from app.core.errors import DomainError, ErrorCode
from app.core.ratelimit import rate_limit_generation, rate_limit_list, rate_limit_send
from app.dashboard import draft_follow_up, send_follow_up
from app.todo import Todo, dismiss_email, dismiss_waiting, save_waiting_days, todo_for

router = APIRouter()


class TodoSettings(BaseModel):
    waitingDays: int = Field(ge=1, le=30)


class FollowUp(BaseModel):
    draft: str = Field(min_length=1, max_length=MAX_DRAFT_CHARS)


@router.get("/todo", dependencies=[Depends(rate_limit_list), Depends(require_mailbox)])
async def get_todo(request: Request) -> Todo:
    return await todo_for(scope_of(request), principal_of(request).email or mailbox.owner())


@router.post("/emails/{message_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_mailbox)])
async def dismiss(message_id: UUID, request: Request) -> None:
    """No reply needed: out of the to-do lists, still in the inbox."""
    if not await dismiss_email(scope_of(request), message_id, is_dismissed=True):
        raise DomainError(ErrorCode.NOT_FOUND)


@router.delete("/emails/{message_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_mailbox)])
async def undismiss(message_id: UUID, request: Request) -> None:
    if not await dismiss_email(scope_of(request), message_id, is_dismissed=False):
        raise DomainError(ErrorCode.NOT_FOUND)


@router.post("/todo/waiting/{sent_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_mailbox)])
async def not_waiting(sent_id: UUID, request: Request) -> None:
    if not await dismiss_waiting(scope_of(request), sent_id):
        raise DomainError(ErrorCode.NOT_FOUND)


@router.post("/todo/waiting/{sent_id}/follow-up",
             dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def follow_up_draft(sent_id: str, request: Request) -> FollowUp:
    """A follow-up to an unanswered reply sent through AIMail, for the user to edit and approve."""
    draft = await draft_follow_up(sent_id, scope=scope_of(request))
    if draft is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return FollowUp(draft=draft)


@router.post("/todo/waiting/{sent_id}/follow-up/send", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(rate_limit_send), Depends(require_mailbox)])
async def follow_up_send(sent_id: str, body: FollowUp, request: Request) -> None:
    if not await send_follow_up(sent_id, body.draft, scope=scope_of(request)):
        raise DomainError(ErrorCode.NOT_FOUND)


@router.put("/settings/todo")
async def put_todo_settings(body: TodoSettings, request: Request) -> TodoSettings:
    user_id = account_user_id(request)
    await save_waiting_days(user_id, body.waitingDays)
    await audit(AuditAction.TODO_SETTINGS, user_id=user_id, waiting_days=body.waitingDays)
    return body
