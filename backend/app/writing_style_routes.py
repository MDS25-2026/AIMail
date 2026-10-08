"""The writing style card's routes (specs/features/writing-profile.md). Per signed-in user only."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.sql.dml import ReturningDelete, ReturningUpdate

from app.account_routes import account_user_id
from app.audit import AuditAction, audit
from app.core.errors import DomainError, ErrorCode
from app.db.models import Message, StyleExample, StyleHabit, WritingStyle
from app.db.session import get_sessionmaker
from app.past_replies import forget_replies
from app.writing_style import (
    MAX_DESCRIPTION_CHARS,
    MAX_EXAMPLE_CHARS,
    MAX_EXAMPLES,
    ExampleSource,
    mask_for_style,
)

router = APIRouter(prefix="/profile/writing")



class ExampleView(BaseModel):
    id: str
    text: str
    source: ExampleSource
    createdAt: datetime


class HabitView(BaseModel):
    id: str
    kind: str
    value: str
    evidence: int
    outOf: int


class WritingStyleView(BaseModel):
    description: str
    learning: bool
    examples: list[ExampleView]
    habits: list[HabitView]
    maxExamples: int = MAX_EXAMPLES


class DescriptionBody(BaseModel):
    description: str = Field(max_length=MAX_DESCRIPTION_CHARS)


class LearningBody(BaseModel):
    enabled: bool


class ExampleBody(BaseModel):
    """Pasted text, or the id of one of the user's sent replies; exactly one."""

    text: str | None = Field(default=None, max_length=MAX_EXAMPLE_CHARS)
    emailId: UUID | None = None

    @model_validator(mode="after")
    def _one_source(self) -> "ExampleBody":
        if (self.text is None) == (self.emailId is None):
            raise ValueError("send text or emailId")
        return self


async def _view(user_id: UUID) -> WritingStyleView:
    async with get_sessionmaker()() as session:
        style = await session.get(WritingStyle, user_id)
        examples = (await session.scalars(select(StyleExample).where(StyleExample.user_id == user_id)
                                          .order_by(StyleExample.created_at))).all()
        habits = (await session.scalars(select(StyleHabit).where(StyleHabit.user_id == user_id, ~StyleHabit.suppressed)
                                        .order_by(StyleHabit.kind, StyleHabit.evidence.desc()))).all()
    return WritingStyleView(
        description=style.description if style else "",
        learning=bool(style and style.learning_enabled),
        examples=[ExampleView(id=str(e.id), text=e.text, source=e.source, createdAt=e.created_at) for e in examples],
        habits=[HabitView(id=str(h.id), kind=h.kind, value=h.value, evidence=h.evidence, outOf=h.out_of)
                for h in habits],
    )


async def _save_style(user_id: UUID, **values: str | bool) -> None:
    statement = insert(WritingStyle).values(user_id=user_id, **values)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(statement.on_conflict_do_update(
            index_elements=["user_id"], set_={**values, "updated_at": func.now()}))


@router.get("")
async def get_style(request: Request) -> WritingStyleView:
    return await _view(account_user_id(request))


@router.put("/description")
async def put_description(body: DescriptionBody, request: Request) -> WritingStyleView:
    """Masked before it is stored; the response shows exactly what the AI will be given."""
    user_id = account_user_id(request)
    description = await mask_for_style(body.description) if body.description.strip() else ""
    await _save_style(user_id, description=description)
    await audit(AuditAction.WRITING_STYLE_DESCRIPTION, user_id=user_id, chars=len(description))
    return await _view(user_id)


@router.put("/learning")
async def put_learning(body: LearningBody, request: Request) -> WritingStyleView:
    user_id = account_user_id(request)
    await _save_style(user_id, learning_enabled=body.enabled)
    await audit(AuditAction.WRITING_STYLE_LEARNING, user_id=user_id, enabled=body.enabled)
    return await _view(user_id)


async def _sent_text(user_id: UUID, email_id: UUID) -> str:
    async with get_sessionmaker()() as session:
        text = await session.scalar(select(Message.draft_reply).where(
            Message.id == email_id, Message.user_id == user_id, Message.sent_at.is_not(None)))
    if not text:
        raise DomainError(ErrorCode.NOT_FOUND)
    return text


@router.post("/examples", status_code=status.HTTP_201_CREATED)
async def add_example(body: ExampleBody, request: Request) -> WritingStyleView:
    user_id = account_user_id(request)
    source = ExampleSource.PASTED if body.text is not None else ExampleSource.SENT
    raw = body.text if body.emailId is None else await _sent_text(user_id, body.emailId)
    if not raw.strip():
        raise DomainError(ErrorCode.EMPTY)
    text = (await mask_for_style(raw))[:MAX_EXAMPLE_CHARS]
    async with get_sessionmaker()() as session, session.begin():
        count = await session.scalar(select(func.count(StyleExample.id)).where(StyleExample.user_id == user_id))
        if count >= MAX_EXAMPLES:
            raise DomainError(ErrorCode.TOO_MANY_EXAMPLES)
        session.add(StyleExample(user_id=user_id, text=text, source=source))
    await audit(AuditAction.WRITING_STYLE_EXAMPLE_ADDED, user_id=user_id, source=source)
    return await _view(user_id)


async def _delete_one(statement: ReturningDelete | ReturningUpdate, user_id: UUID, action: AuditAction,
                      item_id: UUID) -> Response:
    async with get_sessionmaker()() as session, session.begin():
        removed = await session.scalar(statement)
    if removed is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    await audit(action, user_id=user_id, item=item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/examples/{example_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_example(example_id: UUID, request: Request) -> Response:
    user_id = account_user_id(request)
    statement = (delete(StyleExample).where(StyleExample.id == example_id, StyleExample.user_id == user_id)
                 .returning(StyleExample.id))
    return await _delete_one(statement, user_id, AuditAction.WRITING_STYLE_EXAMPLE_DELETED, example_id)


@router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_habit(habit_id: UUID, request: Request) -> Response:
    """Hidden for good: the row stays as a marker so relearning never brings the habit back."""
    user_id = account_user_id(request)
    statement = (update(StyleHabit).where(StyleHabit.id == habit_id, StyleHabit.user_id == user_id)
                 .values(suppressed=True).returning(StyleHabit.id))
    return await _delete_one(statement, user_id, AuditAction.WRITING_STYLE_HABIT_HIDDEN, habit_id)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_everything(request: Request) -> Response:
    """Description, examples, habits, hidden markers, every recorded draft/sent pair and past reply."""
    user_id = account_user_id(request)
    async with get_sessionmaker()() as session, session.begin():
        await session.execute(delete(StyleExample).where(StyleExample.user_id == user_id))
        await session.execute(delete(StyleHabit).where(StyleHabit.user_id == user_id))
        await session.execute(delete(WritingStyle).where(WritingStyle.user_id == user_id))
        await session.execute(update(Message).where(Message.user_id == user_id, Message.edit_ratio.is_not(None))
                              .values(draft_shown=None, edit_ratio=None))
        await forget_replies(session, user_id)
    await audit(AuditAction.WRITING_STYLE_DELETED, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
