"""Holding replies: the user's own words, sent only when they would want them sent.

specs/features/holding-reply.md. This module is the pure part: settings and their validation, when
the reply is active, the conditions an email must meet, and filling in the template. No model ever
writes, edits or translates a holding reply (a protected decision in the spec). Every condition
fails closed: anything that cannot be decided means no reply.
"""

import re
from datetime import date, datetime, time
from email.utils import parseaddr
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.core.language import Language
from app.core.phishing import phishing_signal
from app.db.models import HoldingReplySettings, MaskingStatus, Message

MAX_TEMPLATE_CHARS = 2000
TEMPLATE_FIELD = re.compile(r"\{([a-z_]*)\}")
NAME_FIELD = "name"
RETURN_DATE_FIELD = "return_date"
KNOWN_FIELDS = frozenset({NAME_FIELD, RETURN_DATE_FIELD})
# What {name} becomes when the sender's From header carries no display name.
NAME_FALLBACK = {Language.EN: "there", Language.MS: "tuan/puan", Language.ZH: "您"}
_MALAY_MONTHS = ("Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September",
                 "Oktober", "November", "Disember")
_ENGLISH_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December")


class ActiveWhen(StrEnum):
    OUTSIDE_HOURS = "outside_hours"
    LEAVE = "leave"
    ALWAYS = "always"


class Audience(StrEnum):
    CORRESPONDENTS = "correspondents"
    DOMAIN = "domain"
    EVERYONE = "everyone"


class ReplyScope(StrEnum):
    NEEDS_REPLY = "needs_reply"
    ALL = "all"


class SettingsError(StrEnum):
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


class Refusal(StrEnum):
    """Why an email gets no holding reply. Recorded on cancelled replies; never shown to a sender."""

    DISABLED = "disabled"
    BEFORE_ENABLED = "before_enabled"
    MASKING_PENDING = "masking_pending"
    AUTOMATED = "automated"
    PHISHING = "phishing"
    REPLY_TO_DIFFERS = "reply_to_differs"
    NOT_ACTIVE = "not_active"
    OUTSIDE_DOMAIN = "outside_domain"
    NO_SENDER = "no_sender"
    NO_TEMPLATE = "no_template"
    # Checked when the hold window ends.
    STALE = "stale"
    USER_REPLIED = "user_replied"
    COOLDOWN = "cooldown"
    DAILY_CAP = "daily_cap"
    NO_REPLY_NEEDED = "no_reply_needed"
    NOT_CORRESPONDENT = "not_correspondent"
    NO_THREAD = "no_thread"
    CANCELLED_BY_USER = "cancelled_by_user"


class SettingsBody(BaseModel):
    """The settings as the dashboard sends and receives them (camelCase, like every contract)."""

    enabled: bool = False
    activeWhen: ActiveWhen = ActiveWhen.OUTSIDE_HOURS
    workDays: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5])
    workStart: time = time(9)
    workEnd: time = time(18)
    timezone: str = "Asia/Kuala_Lumpur"
    leaveFrom: date | None = None
    leaveUntil: date | None = None
    audience: Audience = Audience.CORRESPONDENTS
    scope: ReplyScope = ReplyScope.NEEDS_REPLY
    cooldownDays: int = Field(default=4, ge=1, le=30)
    templates: dict[Language, str] = Field(default_factory=dict)
    defaultLanguage: Language = Language.EN


class InvalidSettingsError(ValueError):
    def __init__(self, code: SettingsError) -> None:
        super().__init__(code)
        self.code = code


def _template_errors(body: SettingsBody) -> SettingsError | None:
    for template in body.templates.values():
        fields = set(TEMPLATE_FIELD.findall(template))
        if not template.strip():
            return SettingsError.EMPTY_TEMPLATE
        if len(template) > MAX_TEMPLATE_CHARS:
            return SettingsError.TEMPLATE_TOO_LONG
        if fields - KNOWN_FIELDS:
            return SettingsError.UNKNOWN_PLACEHOLDER
        if RETURN_DATE_FIELD in fields and body.leaveUntil is None:
            return SettingsError.RETURN_DATE_NEEDS_LEAVE
    if body.enabled and body.defaultLanguage not in body.templates:
        return SettingsError.NO_DEFAULT_TEMPLATE
    return None


def _schedule_errors(body: SettingsBody) -> SettingsError | None:
    try:
        ZoneInfo(body.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return SettingsError.UNKNOWN_TIMEZONE
    if not body.workDays or any(day not in range(1, 8) for day in body.workDays):
        return SettingsError.BAD_WORK_DAYS
    if body.workEnd <= body.workStart:
        return SettingsError.WORKDAY_ENDS_BEFORE_IT_STARTS
    if body.activeWhen == ActiveWhen.LEAVE and (body.leaveFrom is None or body.leaveUntil is None):
        return SettingsError.LEAVE_NEEDS_DATES
    if body.leaveFrom and body.leaveUntil and body.leaveUntil < body.leaveFrom:
        return SettingsError.LEAVE_ENDS_BEFORE_IT_STARTS
    return None


def validate(body: SettingsBody) -> None:
    """Raises InvalidSettingsError with the first problem, so the form can say exactly what."""
    error = _schedule_errors(body) or _template_errors(body)
    if error:
        raise InvalidSettingsError(error)


def is_active(settings: HoldingReplySettings, at: datetime) -> bool:
    """Whether the user is away at `at`: outside working hours, on leave, or always."""
    local = at.astimezone(ZoneInfo(settings.timezone))
    on_leave = bool(settings.leave_from and settings.leave_until
                    and settings.leave_from <= local.date() <= settings.leave_until)
    if settings.active_when == ActiveWhen.ALWAYS:
        return True
    if settings.active_when == ActiveWhen.LEAVE:
        return on_leave
    is_working = local.isoweekday() in settings.work_days and settings.work_start <= local.time() < settings.work_end
    return on_leave or not is_working


def address_of(header: str | None) -> str:
    return parseaddr(header or "")[1].strip().lower()


def _domain(address: str) -> str:
    return address.rpartition("@")[2]


def refusal_on_arrival(message: Message, settings: HoldingReplySettings, owner_email: str) -> Refusal | None:
    """The conditions knowable when the email is stored. None means schedule a holding reply."""
    sender = address_of(message.from_addr)
    received = message.received_at or message.created_at
    checks = (
        (not settings.enabled, Refusal.DISABLED),
        (settings.enabled_at is None or received < settings.enabled_at, Refusal.BEFORE_ENABLED),
        (message.masking_status != MaskingStatus.COMPLETE, Refusal.MASKING_PENDING),
        (not sender or sender == owner_email.lower(), Refusal.NO_SENDER),
        (message.is_automated, Refusal.AUTOMATED),
        (phishing_signal(message.body_masked or ""), Refusal.PHISHING),
        (bool(message.reply_to) and address_of(message.reply_to) != sender, Refusal.REPLY_TO_DIFFERS),
        (not is_active(settings, received), Refusal.NOT_ACTIVE),
        (settings.audience == Audience.DOMAIN and _domain(sender) != _domain(owner_email.lower()),
         Refusal.OUTSIDE_DOMAIN),
        (not settings.templates, Refusal.NO_TEMPLATE),
    )
    return next((refusal for is_refused, refusal in checks if is_refused), None)


def choose_language(detected: Language, settings: HoldingReplySettings) -> Language:
    """The sender's language when the user wrote a template for it, else their default."""
    return detected if detected in settings.templates else Language(settings.default_language)


def _format_date(day: date, language: Language) -> str:
    if language == Language.ZH:
        return f"{day.year}年{day.month}月{day.day}日"
    months = _MALAY_MONTHS if language == Language.MS else _ENGLISH_MONTHS
    return f"{day.day} {months[day.month - 1]} {day.year}"


def render(template: str, language: Language, from_header: str | None, leave_until: date | None) -> str:
    """The user's template with {name} and {return_date} filled in locally. Never a model call."""
    display_name = parseaddr(from_header or "")[0].strip()
    values = {
        NAME_FIELD: display_name or NAME_FALLBACK[language],
        RETURN_DATE_FIELD: _format_date(leave_until, language) if leave_until else "",
    }
    return TEMPLATE_FIELD.sub(lambda m: values.get(m.group(1), m.group(0)), template)
