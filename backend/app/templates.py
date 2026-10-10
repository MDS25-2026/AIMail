"""Saved reply templates (specs/features/reply-templates.md): filling, suggesting, translating.

A template's {{variables}} are filled from what AIMail knows without exposing anyone: the sender's
and the owner's names as placeholders (restorable masking fills them in at send), and today's date.
Anything else stays as written, and a draft still holding a {{variable}} cannot be sent.
"""

import re
from datetime import date
from enum import StrEnum

from app.core.language import Language

# One pass over the braces; _key trims the spaces inside (two \s* around a lazy group backtrack badly).
TEMPLATE_VARIABLE = re.compile(r"\{\{([^{}]*)\}\}")
# Stands in for a variable while the template is translated: the translator copies bracketed
# markers exactly, so each variable comes back where it was.
_VARIABLE_MARKER = "[VAR_{}]"
_MARKER = re.compile(r"\[VAR_(\d+)\]")

_MALAY_MONTHS = ("Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September",
                 "Oktober", "November", "Disember")
_ENGLISH_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December")


class Variable(StrEnum):
    NAME = "name"
    MY_NAME = "my name"
    TODAY = "today"


# Each language's own words for the variables AIMail fills, so a Malay or Chinese template can use them.
_ALIASES: dict[str, Variable] = {
    "name": Variable.NAME, "nama": Variable.NAME, "姓名": Variable.NAME, "名字": Variable.NAME,
    "my name": Variable.MY_NAME, "nama saya": Variable.MY_NAME, "我的名字": Variable.MY_NAME,
    "today": Variable.TODAY, "hari ini": Variable.TODAY, "今天": Variable.TODAY,
}


def _key(raw: str) -> str:
    return " ".join(raw.casefold().split())


def format_day(day: date, language: Language) -> str:
    if language == Language.ZH:
        return f"{day.year}年{day.month}月{day.day}日"
    months = _MALAY_MONTHS if language == Language.MS else _ENGLISH_MONTHS
    return f"{day.day} {months[day.month - 1]} {day.year}"


def fill_variables(body: str, *, sender: str | None, owner: str | None, today: str) -> str:
    """The variables AIMail can fill, filled; any other, or one with no value, left as written."""
    values = {Variable.NAME: sender, Variable.MY_NAME: owner, Variable.TODAY: today}

    def fill(match: re.Match[str]) -> str:
        variable = _ALIASES.get(_key(match.group(1)))
        return (values.get(variable) if variable else None) or match.group(0)

    return TEMPLATE_VARIABLE.sub(fill, body)


def has_unfilled_variable(text: str) -> bool:
    return TEMPLATE_VARIABLE.search(text) is not None


def matching_template_id(templates: list[tuple[str, str, list[str]]], language: Language, text: str) -> str | None:
    """The first template in the given order whose language matches and one of whose trigger
    words appears in the email. Each template is (id, language, trigger words)."""
    folded = text.casefold()
    for template_id, template_language, triggers in templates:
        if template_language == language and any(t.strip() and t.casefold() in folded for t in triggers):
            return template_id
    return None


def protect_variables(body: str) -> tuple[str, list[str]]:
    """The body with each {{variable}} as a numbered marker, and the variables in order."""
    variables: list[str] = []

    def mark(match: re.Match[str]) -> str:
        variables.append(match.group(0))
        return _VARIABLE_MARKER.format(len(variables))

    return TEMPLATE_VARIABLE.sub(mark, body), variables


def restore_variables(translated: str, variables: list[str]) -> str | None:
    """The markers back as variables; None when the translation lost or invented one."""
    found = [int(n) for n in _MARKER.findall(translated)]
    if sorted(found) != list(range(1, len(variables) + 1)):
        return None
    return _MARKER.sub(lambda match: variables[int(match.group(1)) - 1], translated)
