"""Names in text a person typed, hidden from the model for one request (specs/features/privacy-gaps.md).

Presidio's English model finds most names; app/core/name_patterns.py adds the Malaysian shapes it
misses. Run after ThreadMap.tokenise_known and mask_typed_text, so only names AIMail does not already
know are left. The caller puts the names back into whatever the model returns before it is stored or shown.
"""

import re

from app.core.name_patterns import find_name_patterns
from app.rag.mask import find_people

# Past any thread's own numbers, below the owner's and the sender's fixed 900 and 901.
FIRST_TYPED_NUMBER = 800
LAST_TYPED_NUMBER = 899
# Never filled in, so a draft holding it cannot be sent (has_redaction_marker).
OVERFLOW_MARKER = "[Redacted]"

AgentValue = str | int | float | bool | None | list["AgentValue"] | dict[str, "AgentValue"]


_HAN = re.compile(r"[\u4e00-\u9fff]")


def _whole_words(name: str) -> re.Pattern[str]:
    words = r"\s+".join(map(re.escape, name.split()))
    # Chinese has no spaces between words, so a name written in characters is matched as it stands.
    return re.compile(words if _HAN.search(name) else rf"(?<!\w){words}(?!\w)", re.IGNORECASE)


class TypedNames:
    """One request's new names; the same name keeps one placeholder across every text it hides."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}  # placeholder -> the name as typed

    async def hide(self, text: str) -> str:
        if not text.strip():
            return text
        found = {name.strip() for name in [*await find_people(text), *find_name_patterns(text)] if name.strip()}
        # Longest first, so "Aisyah binti Ali" is one name before "Ali" can match inside it.
        for name in sorted(found, key=len, reverse=True):
            text = _whole_words(name).sub(self._placeholder(name), text)
        return text

    def restore(self, text: str) -> str:
        for placeholder, name in self.names.items():
            text = text.replace(placeholder, name)
        return text

    def restore_answer(self, answer: dict[str, AgentValue]) -> dict[str, AgentValue]:
        """The names back in every string of an agent answer: the draft, the summary, the reasons."""
        return {key: self._restored(value) for key, value in answer.items()}

    def _restored(self, value: AgentValue) -> AgentValue:
        if isinstance(value, str):
            return self.restore(value)
        if isinstance(value, list):
            return [self._restored(item) for item in value]
        if isinstance(value, dict):
            return self.restore_answer(value)
        return value

    def _placeholder(self, name: str) -> str:
        known = next((p for p, typed in self.names.items() if typed.lower() == name.lower()), None)
        if known:
            return known
        number = FIRST_TYPED_NUMBER + len(self.names)
        if number > LAST_TYPED_NUMBER:
            return OVERFLOW_MARKER
        placeholder = f"[PERSON_{number}]"
        self.names[placeholder] = name
        return placeholder
