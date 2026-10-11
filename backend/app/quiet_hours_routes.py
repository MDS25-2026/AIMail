"""Settings > Quiet hours (specs/features/quiet-hours-send-later.md). Per signed-in user only."""

from fastapi import APIRouter, Request

from app.account_routes import account_user_id
from app.audit import AuditAction, audit
from app.quiet_hours import (
    QuietHoursSettings,
    QuietHoursView,
    follow_company,
    save,
    settings_for,
)

router = APIRouter()


@router.get("/settings/quiet-hours")
async def get_quiet_hours(request: Request) -> QuietHoursSettings:
    return await settings_for(account_user_id(request))


@router.put("/settings/quiet-hours")
async def put_quiet_hours(body: QuietHoursView, request: Request) -> QuietHoursSettings:
    """The user's own quiet hours, replacing the company default for them."""
    user_id = account_user_id(request)
    await save(user_id, body)
    await audit(AuditAction.QUIET_HOURS, user_id=user_id, personal=True)
    return await settings_for(user_id)


@router.delete("/settings/quiet-hours")
async def delete_quiet_hours(request: Request) -> QuietHoursSettings:
    """Back to the company default."""
    user_id = account_user_id(request)
    await follow_company(user_id)
    await audit(AuditAction.QUIET_HOURS, user_id=user_id, personal=False)
    return await settings_for(user_id)
