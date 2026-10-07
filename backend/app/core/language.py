"""Which language an email is written in: en, ms or zh. A local heuristic, never a model call.

Chinese characters mean Chinese. Otherwise common words tell Malay from English; anything else, or
nothing to judge by, is English. The dashboard's Translate check (src/lib/detectLanguage.ts) uses
the same word lists.
"""

import re
from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    MS = "ms"
    ZH = "zh"


_ENGLISH = frozenset({
    "the", "and", "to", "of", "you", "is", "for", "in", "that", "this", "with", "we", "your",
    "please", "thank", "thanks", "are", "be", "have", "will", "our", "on", "it", "at", "as", "from",
    "can", "if", "would", "i",
})
_MALAY = frozenset({
    "dan", "yang", "untuk", "dengan", "ini", "itu", "tidak", "anda", "saya", "kami", "ada", "pada",
    "akan", "dari", "boleh", "sila", "terima", "kasih", "adalah", "dalam", "kepada", "telah",
    "sudah", "juga", "atau", "bagi", "oleh", "mohon",
})
_HAN = re.compile("[一-鿿]")
_WORD = re.compile(r"[^\W\d_]+")
_PLACEHOLDER = re.compile(r"\[[A-Z_]+\d*\]")


def detect_language(text: str) -> Language:
    clean = _PLACEHOLDER.sub(" ", text)
    if _HAN.search(clean):
        return Language.ZH
    words = _WORD.findall(clean.lower())
    malay = sum(word in _MALAY for word in words)
    english = sum(word in _ENGLISH for word in words)
    return Language.MS if malay > english else Language.EN
