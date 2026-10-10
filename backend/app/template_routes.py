"""Saved reply templates (specs/features/reply-templates.md). Per signed-in user only."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, StringConstraints

from app.account_routes import account_user_id
from app.agent_contract import Tone
from app.audit import AuditAction, audit
from app.contracts import DashboardEmail
from app.core.auth import require_mailbox, scope_of
from app.core.constants import (
    MAX_TEMPLATE_BODY_CHARS,
    MAX_TEMPLATE_TITLE_CHARS,
    MAX_TEMPLATE_TRIGGER_CHARS,
    MAX_TEMPLATE_TRIGGERS,
)
from app.core.errors import DomainError, ErrorCode
from app.core.language import Language
from app.core.ratelimit import rate_limit_generation
from app.dashboard import adapt_template, fill_template, translate_template
from app.db.models import ReplyTemplate
from app.template_store import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    mark_used,
    update_template,
)

router = APIRouter()

Trigger = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEMPLATE_TRIGGER_CHARS)]


class TemplateBody(BaseModel):
    title: str = Field(min_length=1, max_length=MAX_TEMPLATE_TITLE_CHARS)
    body: str = Field(min_length=1, max_length=MAX_TEMPLATE_BODY_CHARS)
    language: Language
    triggerKeywords: list[Trigger] = Field(default_factory=list, max_length=MAX_TEMPLATE_TRIGGERS)


class TemplateView(TemplateBody):
    id: str
    lastUsedAt: str | None = None


class FillRequest(BaseModel):
    emailId: str


class FilledTemplate(BaseModel):
    text: str


class AdaptRequest(BaseModel):
    emailId: str
    tone: Tone = Tone.PROFESSIONAL


class TranslateTemplateRequest(BaseModel):
    language: Language


def _view(template: ReplyTemplate) -> TemplateView:
    return TemplateView(id=str(template.id), title=template.title, body=template.body,
                        language=Language(template.language), triggerKeywords=template.trigger_keywords or [],
                        lastUsedAt=template.last_used_at.isoformat() if template.last_used_at else None)


def _columns(body: TemplateBody) -> dict:
    return {"title": body.title, "body": body.body, "language": body.language.value,
            "trigger_keywords": body.triggerKeywords}


async def _owned(request: Request, template_id: UUID) -> ReplyTemplate:
    template = await get_template(account_user_id(request), template_id)
    if template is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return template


@router.get("/templates")
async def get_templates(request: Request) -> list[TemplateView]:
    return [_view(t) for t in await list_templates(account_user_id(request))]


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def post_template(body: TemplateBody, request: Request) -> TemplateView:
    user_id = account_user_id(request)
    template = await create_template(user_id, _columns(body))
    await audit(AuditAction.TEMPLATE_SAVED, user_id=user_id, template=template.id)
    return _view(template)


@router.put("/templates/{template_id}")
async def put_template(template_id: UUID, body: TemplateBody, request: Request) -> TemplateView:
    user_id = account_user_id(request)
    template = await update_template(user_id, template_id, _columns(body))
    if template is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    await audit(AuditAction.TEMPLATE_SAVED, user_id=user_id, template=template_id)
    return _view(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_template(template_id: UUID, request: Request) -> None:
    user_id = account_user_id(request)
    if not await delete_template(user_id, template_id):
        raise DomainError(ErrorCode.NOT_FOUND)
    await audit(AuditAction.TEMPLATE_DELETED, user_id=user_id, template=template_id)


@router.post("/templates/{template_id}/fill", dependencies=[Depends(require_mailbox)])
async def fill_template_route(template_id: UUID, body: FillRequest, request: Request) -> FilledTemplate:
    """The template filled for one email, for the editor (Insert). Nothing is stored or sent."""
    template = await _owned(request, template_id)
    text = await fill_template(body.emailId, template, scope=scope_of(request))
    if text is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    await mark_used(template.id)
    await audit(AuditAction.TEMPLATE_USED, user_id=template.user_id, template=template.id, mode="insert")
    return FilledTemplate(text=text)


@router.post("/templates/{template_id}/adapt",
             dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def adapt_template_route(template_id: UUID, body: AdaptRequest, request: Request) -> DashboardEmail:
    """The agent rewrites the template for the email (Draft from template); stored like a refine."""
    template = await _owned(request, template_id)
    email = await adapt_template(body.emailId, template, scope=scope_of(request), tone=body.tone)
    if email is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    await mark_used(template.id)
    await audit(AuditAction.TEMPLATE_USED, user_id=template.user_id, template=template.id, mode="adapt")
    return email


@router.post("/templates/{template_id}/translate", dependencies=[Depends(rate_limit_generation)])
async def translate_template_route(
    template_id: UUID, body: TranslateTemplateRequest, request: Request
) -> TemplateBody:
    """A copy in another language for the user to check; not saved until they save it."""
    template = await _owned(request, template_id)
    translated = await translate_template(template, body.language)
    return TemplateBody(title=template.title, body=translated, language=body.language,
                        triggerKeywords=template.trigger_keywords or [])
