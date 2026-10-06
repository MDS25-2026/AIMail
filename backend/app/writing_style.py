"""Writing style: how the user writes, in their own control (specs/features/writing-profile.md).

Three sources, any mix: a description, up to three example replies, and habits learned from sends
while the user has learning switched on. Everything is masked before it is stored, and no model is
trained: the style reaches the agent as a short fenced hint plus the examples.
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redaction import ANY_MASK, PLACEHOLDER
from app.db.models import Message, StyleExample, StyleHabit, WritingStyle
from app.rag.mask import mask_document

logger = logging.getLogger(__name__)

MAX_EXAMPLES = 3
MAX_EXAMPLE_CHARS = 1500
MAX_DESCRIPTION_CHARS = 300
STYLE_HINT_CHARS = 1200
MIN_EVIDENCE = 3
LEARN_WINDOW = 20
# Above this a reply was rewritten, not edited: it says the draft missed, not how the user phrases.
REWRITE_RATIO = 0.8
MAX_SWAP_WORDS = 4
MAX_GREETING_WORDS = 6
MAX_SIGNOFF_WORDS = 5
# Words, not characters: replies in a mailbox vary too much for a finer scale to mean anything.
SHORT_REPLY_WORDS = 60
LONG_REPLY_WORDS = 150
# What every masked detail becomes, so no bracketed mark from another email can reach a draft.
HIDDEN = "(hidden)"
NAME = "(name)"
LINE_BREAK = "\n"

_GREETINGS = re.compile(
    r"^(hi|hello|hey|dear|good (morning|afternoon|evening)|salam|assalamualaikum|hai|selamat"
    r"|您好|你好|各位)\b", re.IGNORECASE)
_SIGNOFFS = re.compile(
    r"^(thanks|thank you|regards|best|cheers|sincerely|warm|kind|many thanks|terima kasih|salam"
    r"|sekian|谢谢|此致|祝好)", re.IGNORECASE)
# One to three capitalised words: the shape of a name signed under a closing.
_SIGNATURE = re.compile(r"[A-Z][\w'-]*(?: [A-Z][\w'-]*){0,2}")
_UNSAFE = re.compile(r"\d|@|https?://|www\.|\[|\]")
_CAPITALISED = re.compile(r"\b[A-Z][a-z]+")
_SENTENCE_START = re.compile(r"(?:^|[.!?]\s+)([A-Z][a-z]+)")


class HabitKind(StrEnum):
    GREETING = "greeting"
    SIGNOFF = "signoff"
    LENGTH = "length"
    SWAP = "swap"


class ReplyLength(StrEnum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class ExampleSource(StrEnum):
    PASTED = "pasted"
    SENT = "sent"


@dataclass(frozen=True)
class Habit:
    kind: HabitKind
    value: str
    evidence: int
    out_of: int


@dataclass(frozen=True)
class Style:
    """What a draft request carries. Empty when the user has set nothing."""

    hint: str = ""
    examples: list[str] = field(default_factory=list)


def neutralise(text: str) -> str:
    """Every placeholder and masking mark as one plain word, so none can be copied into a draft."""
    return ANY_MASK.sub(HIDDEN, text)


def hide_closing_name(text: str) -> str:
    """A short capitalised last line under a closing is a signature, whatever Presidio made of it."""
    lines = text.rstrip().split("\n")
    if len(lines) < 2 or not _SIGNOFFS.match(lines[-2].strip()) or not _SIGNATURE.fullmatch(lines[-1].strip()):
        return text
    return "\n".join([*lines[:-1], HIDDEN])


async def mask_for_style(text: str) -> str:
    """Masked and neutralised. Raises DocumentMaskingError when the masker is unreachable."""
    return hide_closing_name(neutralise(await mask_document(neutralise(text.strip()))))


def edit_ratio(shown: str, sent: str) -> float:
    """Word-level Levenshtein distance over the longer text: 0 sent as shown, 1 rewritten."""
    before, after = shown.split(), sent.split()
    if not before and not after:
        return 0.0
    previous = list(range(len(after) + 1))
    for i, word in enumerate(before, 1):
        current = [i]
        for j, other in enumerate(after, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (word != other)))
        previous = current
    return previous[-1] / max(len(before), len(after))


def is_safe_phrase(phrase: str) -> bool:
    """The PII screen: no digit, @, link, mark, or capitalised word that is not a sentence start."""
    if not phrase or _UNSAFE.search(phrase) or HIDDEN in phrase:
        return False
    starts = {m.start(1) for m in _SENTENCE_START.finditer(phrase)}
    return all(m.start() in starts or m.group() == "I" for m in _CAPITALISED.finditer(phrase))


def _with_names(text: str) -> str:
    return PLACEHOLDER.sub(lambda m: NAME if m.group(1) == "PERSON" else HIDDEN, text)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in _with_names(text).splitlines() if line.strip()]


def greeting_of(text: str) -> str | None:
    lines = _lines(text)
    first = lines[0] if lines else ""
    if len(first.split()) > MAX_GREETING_WORDS or not _GREETINGS.match(first):
        return None
    return first


def signoff_of(text: str) -> str | None:
    """The closing phrase, never the name under it: the name is the backend's to choose."""
    for line in reversed(_lines(text)[-3:]):
        phrase = line.partition(NAME)[0].strip()
        if _SIGNOFFS.match(phrase) and len(phrase.split()) <= MAX_SIGNOFF_WORDS:
            return phrase
    return None


def length_of(text: str) -> ReplyLength:
    words = len(text.split())
    if words < SHORT_REPLY_WORDS:
        return ReplyLength.SHORT
    return ReplyLength.LONG if words > LONG_REPLY_WORDS else ReplyLength.MEDIUM


def _tokens(text: str) -> list[str]:
    """Words with a line break as its own token, so edits on neighbouring lines stay separate."""
    return [token for line in _with_names(text).splitlines() for token in (*line.split(), LINE_BREAK)]


def _starts_sentence(tokens: list[str], index: int) -> bool:
    return index == 0 or tokens[index - 1] == LINE_BREAK or tokens[index - 1][-1:] in ".!?"


def _is_safe_fragment(tokens: list[str], start: int, end: int) -> bool:
    """A fragment's first word only counts as a sentence start if it is one in the reply."""
    phrase = " ".join(tokens[start:end])
    is_capital_start = phrase[:1].isupper() and phrase.split()[0] != "I"
    return is_safe_phrase(phrase) and not (is_capital_start and not _starts_sentence(tokens, start))


def swaps_of(shown: str, sent: str) -> set[str]:
    """Short phrases the user replaced, as "old → new"; each counted once per reply."""
    before, after = _tokens(shown), _tokens(sent)
    found = set()
    for op, i1, i2, j1, j2 in SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes():
        is_short = 0 < i2 - i1 <= MAX_SWAP_WORDS and 0 < j2 - j1 <= MAX_SWAP_WORDS
        is_one_line = LINE_BREAK not in before[i1:i2] + after[j1:j2]
        if op == "replace" and is_short and is_one_line and _is_safe_fragment(before, i1, i2) \
                and _is_safe_fragment(after, j1, j2):
            found.add(f"{' '.join(before[i1:i2])} → {' '.join(after[j1:j2])}")
    return found


def _top(values: list[str], kind: HabitKind, out_of: int) -> list[Habit]:
    counts = Counter(v for v in values if is_safe_phrase(v))
    if not counts:
        return []
    value, evidence = counts.most_common(1)[0]
    return [Habit(kind, value, evidence, out_of)] if evidence >= MIN_EVIDENCE else []


def learn(pairs: list[tuple[str, str, float]]) -> list[Habit]:
    """Habits from (shown, sent, ratio) pairs, newest first. Pure: the caller stores them."""
    sents = [sent for _, sent, _ in pairs]
    edited = [(shown, sent) for shown, sent, ratio in pairs if ratio <= REWRITE_RATIO and shown]
    lengths = Counter(length_of(sent) for sent in sents).most_common(1)
    habits = [
        *_top([g for g in map(greeting_of, sents) if g], HabitKind.GREETING, len(sents)),
        *_top([s for s in map(signoff_of, sents) if s], HabitKind.SIGNOFF, len(sents)),
        *[Habit(HabitKind.LENGTH, value, n, len(sents)) for value, n in lengths if n >= MIN_EVIDENCE],
    ]
    swaps = Counter(swap for shown, sent in edited for swap in swaps_of(shown, sent))
    habits += [Habit(HabitKind.SWAP, swap, n, len(edited)) for swap, n in swaps.items() if n >= MIN_EVIDENCE]
    return habits


async def is_learning(session: AsyncSession, user_id: UUID | None) -> bool:
    if user_id is None:
        return False
    style = await session.get(WritingStyle, user_id)
    return bool(style and style.learning_enabled)


async def relearn(session: AsyncSession, user_id: UUID) -> None:
    """Replace the user's learned habits from their recent recorded sends; deleted ones stay hidden."""
    rows = (await session.execute(
        select(Message.draft_shown, Message.draft_reply, Message.edit_ratio)
        .where(Message.user_id == user_id, Message.edit_ratio.is_not(None))
        .order_by(Message.sent_at.desc()).limit(LEARN_WINDOW)
    )).all()
    pairs = [(shown or "", sent or "", ratio) for shown, sent, ratio in rows]
    hidden = set((await session.execute(
        select(StyleHabit.kind, StyleHabit.value).where(StyleHabit.user_id == user_id, StyleHabit.suppressed)
    )).all())
    await session.execute(delete(StyleHabit).where(StyleHabit.user_id == user_id, ~StyleHabit.suppressed))
    session.add_all(
        StyleHabit(user_id=user_id, kind=h.kind, value=h.value, evidence=h.evidence, out_of=h.out_of)
        for h in learn(pairs) if (h.kind, h.value) not in hidden
    )


def _habit_line(habit: StyleHabit) -> str:
    match habit.kind:
        case HabitKind.GREETING if NAME in habit.value:
            # Never quoted with the mark itself: a model copies a quoted "(name)" into the draft.
            return f'Opens with "{habit.value.partition(NAME)[0].strip()}" and the recipient\'s name.'
        case HabitKind.GREETING:
            return f'Opens with "{habit.value}".'
        case HabitKind.SIGNOFF:
            return f'Closes with "{habit.value}" before the sign-off name.'
        case HabitKind.LENGTH:
            return f"Keeps replies {habit.value}."
        case _:
            old, _, new = habit.value.partition(" → ")
            return f'Writes "{new}" rather than "{old}".'


async def style_for(session: AsyncSession, user_id: UUID | None) -> Style:
    """The hint and examples a draft for this user carries. Legacy rows with no owner get none."""
    if user_id is None:
        return Style()
    style = await session.get(WritingStyle, user_id)
    habits = (await session.scalars(
        select(StyleHabit).where(StyleHabit.user_id == user_id, ~StyleHabit.suppressed)
        .order_by(StyleHabit.kind, StyleHabit.evidence.desc())
    )).all()
    examples = (await session.scalars(
        select(StyleExample.text).where(StyleExample.user_id == user_id)
        .order_by(StyleExample.created_at).limit(MAX_EXAMPLES)
    )).all()
    lines = [style.description] if style and style.description else []
    hint = "\n".join([*lines, *map(_habit_line, habits)])[:STYLE_HINT_CHARS]
    return Style(hint=hint, examples=[text[:MAX_EXAMPLE_CHARS] for text in examples])
