"""Settings > Account: disconnect Gmail, delete the account (app/account.py)."""

from uuid import UUID

from fastapi import APIRouter, Request, Response, status

from app import account
from app.core.auth import principal_of
from app.core.errors import DomainError, ErrorCode
from app.sign_in import clear_session

router = APIRouter(prefix="/account")



def account_user_id(request: Request) -> UUID:
    """Only a signed-in person has an account; a script with the shared token does not."""
    user_id = principal_of(request).user_id
    if user_id is None:
        raise DomainError(ErrorCode.ACCOUNT_ONLY)
    return user_id


@router.delete("/gmail", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_gmail(request: Request) -> Response:
    try:
        await account.disconnect_gmail(account_user_id(request))
    except account.NotConnectedError as exc:
        raise DomainError(ErrorCode.NOT_CONNECTED) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(request: Request) -> Response:
    try:
        await account.delete_account(account_user_id(request))
    except account.AccountDeletionError as exc:
        raise DomainError(ErrorCode.ACCOUNT_NOT_FULLY_DELETED) from exc
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_session(response)
    return response
