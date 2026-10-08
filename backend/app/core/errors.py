"""Every error the API can answer, in one registry and one envelope (specs/context/backbone-contracts.md).

Domain code raises DomainError(ErrorCode.X) and never chooses an HTTP status; the table below does. Every
response is {"error": {"code", "message"}}; the dashboard maps the code to its own words.
"""

import logging
from enum import StrEnum

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    # Request shape and lookups
    INVALID_REQUEST = "invalid_request"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    TOO_LARGE = "too_large"
    NOT_PDF = "not_pdf"
    UNREADABLE_PDF = "unreadable_pdf"
    EMPTY = "empty"
    TOO_LONG = "too_long"
    # Sign-in and accounts
    SIGNED_OUT = "signed_out"
    SESSION_INVALID = "session_invalid"
    CLIENT_HEADER_MISSING = "client_header_missing"
    ACCOUNT_ONLY = "account_only"
    NOT_CONNECTED = "not_connected"
    ACCOUNT_NOT_FULLY_DELETED = "account_not_fully_deleted"
    ADMIN_AUTH_NOT_CONFIGURED = "admin_auth_not_configured"
    ADMIN_SIGNED_OUT = "admin_signed_out"
    ADMIN_SESSION_INVALID = "admin_session_invalid"
    NOT_AN_ADMIN = "not_an_admin"
    INVALID_CREDENTIALS = "invalid_credentials"
    ADMIN_HEADER_MISSING = "admin_header_missing"
    # Drafting and sending
    ALREADY_SENT = "already_sent"
    MASKING_PENDING = "masking_pending"
    SENDER_UNVERIFIED = "sender_unverified"
    DRAFT_REFUSED = "draft_refused"
    AGENT_UNAVAILABLE = "agent_unavailable"
    REDACTION_MARKERS = "redaction_markers"
    UNRESOLVED_PLACEHOLDERS = "unresolved_placeholders"
    SEND_NOT_GRANTED = "send_not_granted"
    SEND_FAILED = "send_failed"
    SEND_OUTCOME_UNKNOWN = "send_outcome_unknown"
    GOOGLE_ACCESS_EXPIRED = "google_access_expired"
    TRANSLATION_UNFAITHFUL = "translation_unfaithful"
    # Features
    PRIVATE_MODE_UNAVAILABLE = "private_mode_unavailable"
    TOO_MANY_EXAMPLES = "too_many_examples"
    ALREADY_SENT_OR_CANCELLED = "already_sent_or_cancelled"
    INVALID_SETTINGS = "invalid_settings"
    # Holding-reply settings that could never work (app/holding_reply.py validates them)
    UNKNOWN_PLACEHOLDER = "unknown_placeholder"
    RETURN_DATE_NEEDS_LEAVE = "return_date_needs_leave"
    EMPTY_TEMPLATE = "empty_template"
    TEMPLATE_TOO_LONG = "template_too_long"
    NO_DEFAULT_TEMPLATE = "no_default_template"
    UNKNOWN_TIMEZONE = "unknown_timezone"
    LEAVE_NEEDS_DATES = "leave_needs_dates"
    LEAVE_ENDS_BEFORE_IT_STARTS = "leave_ends_before_it_starts"
    WORKDAY_ENDS_BEFORE_IT_STARTS = "workday_ends_before_it_starts"
    BAD_WORK_DAYS = "bad_work_days"
    # Dependencies
    MASKING_UNAVAILABLE = "masking_unavailable"
    AI_SERVICE_UNREACHABLE = "ai_service_unreachable"
    SUPABASE_UNAVAILABLE = "supabase_unavailable"
    DATABASE_UNREACHABLE = "database_unreachable"
    DATABASE_ERROR = "database_error"
    INTERNAL = "internal"


_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_REQUEST: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.EMPTY: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.TOO_LONG: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.INVALID_SETTINGS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.UNKNOWN_PLACEHOLDER: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.RETURN_DATE_NEEDS_LEAVE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.EMPTY_TEMPLATE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.TEMPLATE_TOO_LONG: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.NO_DEFAULT_TEMPLATE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.UNKNOWN_TIMEZONE: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.LEAVE_NEEDS_DATES: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.LEAVE_ENDS_BEFORE_IT_STARTS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.WORKDAY_ENDS_BEFORE_IT_STARTS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.BAD_WORK_DAYS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.DRAFT_REFUSED: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.REDACTION_MARKERS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.UNRESOLVED_PLACEHOLDERS: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.TRANSLATION_UNFAITHFUL: status.HTTP_422_UNPROCESSABLE_CONTENT,
    ErrorCode.NOT_PDF: status.HTTP_400_BAD_REQUEST,
    ErrorCode.UNREADABLE_PDF: status.HTTP_400_BAD_REQUEST,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.NOT_CONNECTED: status.HTTP_404_NOT_FOUND,
    ErrorCode.CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.ALREADY_SENT: status.HTTP_409_CONFLICT,
    ErrorCode.MASKING_PENDING: status.HTTP_409_CONFLICT,
    ErrorCode.SENDER_UNVERIFIED: status.HTTP_409_CONFLICT,
    ErrorCode.GOOGLE_ACCESS_EXPIRED: status.HTTP_409_CONFLICT,
    ErrorCode.PRIVATE_MODE_UNAVAILABLE: status.HTTP_409_CONFLICT,
    ErrorCode.TOO_MANY_EXAMPLES: status.HTTP_409_CONFLICT,
    ErrorCode.ALREADY_SENT_OR_CANCELLED: status.HTTP_409_CONFLICT,
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.ACCOUNT_ONLY: status.HTTP_403_FORBIDDEN,
    ErrorCode.CLIENT_HEADER_MISSING: status.HTTP_403_FORBIDDEN,
    ErrorCode.SEND_NOT_GRANTED: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_AN_ADMIN: status.HTTP_403_FORBIDDEN,
    ErrorCode.ADMIN_HEADER_MISSING: status.HTTP_403_FORBIDDEN,
    ErrorCode.SIGNED_OUT: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.SESSION_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.ADMIN_SIGNED_OUT: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.ADMIN_SESSION_INVALID: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.INVALID_CREDENTIALS: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.TOO_LARGE: status.HTTP_413_CONTENT_TOO_LARGE,
    ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.AGENT_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.SEND_FAILED: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.ACCOUNT_NOT_FULLY_DELETED: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.SEND_OUTCOME_UNKNOWN: status.HTTP_504_GATEWAY_TIMEOUT,
    ErrorCode.MASKING_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.AI_SERVICE_UNREACHABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.SUPABASE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.DATABASE_UNREACHABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.ADMIN_AUTH_NOT_CONFIGURED: status.HTTP_503_SERVICE_UNAVAILABLE,
    ErrorCode.DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ErrorCode.INTERNAL: status.HTTP_500_INTERNAL_SERVER_ERROR,
}

# An HTTPException raised by a framework part (or a plain status) still answers with a registered code.
_CODE_FOR_STATUS: dict[int, ErrorCode] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.INVALID_REQUEST,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.SIGNED_OUT,
    status.HTTP_403_FORBIDDEN: ErrorCode.FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.NOT_FOUND,
    status.HTTP_409_CONFLICT: ErrorCode.CONFLICT,
    status.HTTP_413_CONTENT_TOO_LARGE: ErrorCode.TOO_LARGE,
    status.HTTP_422_UNPROCESSABLE_CONTENT: ErrorCode.INVALID_REQUEST,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}


def status_for(code: ErrorCode) -> int:
    return _STATUS[code]


class DomainError(Exception):
    """A refusal the caller can act on. The status comes from the registry, never from the raise site."""

    def __init__(self, code: ErrorCode, message: str = "") -> None:
        super().__init__(message or code.value)
        self.code = code
        self.message = message or code.value

    @property
    def status_code(self) -> int:
        return status_for(self.code)


def error_response(code: ErrorCode, message: str = "", headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_for(code), headers=headers,
                        content={"error": {"code": code.value, "message": message or code.value}})


def _code_of(exc: HTTPException) -> ErrorCode:
    detail = exc.detail if isinstance(exc.detail, str) else ""
    if detail in ErrorCode._value2member_map_:
        return ErrorCode(detail)
    return _CODE_FOR_STATUS.get(exc.status_code, ErrorCode.INTERNAL)


async def _domain_error(_request: Request, exc: DomainError) -> JSONResponse:
    return error_response(exc.code, exc.message)


async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    code = _code_of(exc)
    # The status stays the raiser's: a framework 405 is still a 405, just in the shared envelope.
    response = error_response(code, str(exc.detail), headers=exc.headers)
    response.status_code = exc.status_code
    return response


async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
    return error_response(ErrorCode.INVALID_REQUEST, f"invalid fields: {fields}")


async def _database_unreachable(request: Request, _exc: Exception) -> JSONResponse:
    # Usually a wrong DATABASE_URL or a paused Supabase project; retrying later is the right answer.
    logger.warning("database unreachable on %s", request.url.path)
    return error_response(ErrorCode.DATABASE_UNREACHABLE)


async def _database_error(request: Request, exc: Exception) -> JSONResponse:
    # A connection the pooler dropped mid-query is an outage; any other DBAPI fault is our bug.
    if getattr(exc, "connection_invalidated", False):
        return await _database_unreachable(request, exc)
    logger.exception("database error on %s", request.url.path)
    return error_response(ErrorCode.DATABASE_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(HTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    for exc_type in (OSError, OperationalError, InterfaceError):
        app.add_exception_handler(exc_type, _database_unreachable)
    # After the specific handlers so those still win for their own types.
    app.add_exception_handler(DBAPIError, _database_error)
