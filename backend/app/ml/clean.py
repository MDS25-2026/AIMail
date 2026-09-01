"""Normalize raw email text before it reaches the classifier.

The annotation unit is the WHOLE thread (labels consider requests anywhere in the visible history),
so this deliberately keeps quoted/forwarded content — it only removes encoding noise that carries no
signal: quoted-printable artifacts (`=20`, soft-break `=\n`) and redundant whitespace. Applied
identically at train and inference time so the model always sees the same shape of text.

(An earlier version truncated to the newest message; that misaligned with the whole-thread rubric —
it stripped the exact context the labels depend on — and is intentionally not done here.)
"""

import quopri
import re

_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _decode_quoted_printable(text: str) -> str:
    # Only bother if the tell-tale artifacts are present (soft-break "=\n" or "=20"-style codes).
    if "=\n" not in text and not re.search(r"=[0-9A-Fa-f]{2}", text):
        return text
    return quopri.decodestring(text.encode("utf-8", "replace")).decode("utf-8", "replace")


def clean_email_text(raw: str) -> str:
    text = _decode_quoted_printable(raw)
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()
