"""Clean raw email text before it reaches the classifier.

Measured on the training set, ~24% of emails were truncated at the token limit and ~31% carried
forwarded/quoted thread history — noise the model had to see through. This extracts the newest
message only (dropping quoted replies and forwarded blocks), decodes quoted-printable artifacts,
and normalizes whitespace. Applied identically at train and inference time so the model always sees
the same shape of text.
"""

import quopri
import re

# Markers where the newest message ends and quoted history / forwarded content begins. Cut at the
# earliest one found. Ordered by how unambiguous each marker is.
_HISTORY_MARKERS = [
    re.compile(r"-{2,}\s*original message\s*-{2,}", re.IGNORECASE),
    re.compile(r"-{3,}.*forwarded by", re.IGNORECASE),
    re.compile(r"\n_{10,}"),                                  # Outlook underscore separator
    re.compile(r"\nOn .{1,120}? wrote:", re.IGNORECASE),      # "On <date>, <name> wrote:"
    re.compile(r"\n\s*\S+@\S+\s+on\s+\d{1,2}/\d{1,2}/\d{2,4}"),  # Enron "name@x.com on 03/20/2001"
    re.compile(r"\n\s*From:\s.+\n\s*(Sent|To|Date):", re.IGNORECASE),  # quoted header block
]

_QUOTED_LINE = re.compile(r"(?m)^\s*>.*$")   # ">" quoted reply lines
_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_LINES = re.compile(r"\n{3,}")


def _decode_quoted_printable(text: str) -> str:
    # Only bother if the tell-tale artifacts are present (soft-break "=\n" or "=20"-style codes).
    if "=\n" not in text and not re.search(r"=[0-9A-Fa-f]{2}", text):
        return text
    return quopri.decodestring(text.encode("utf-8", "replace")).decode("utf-8", "replace")


def clean_email_text(raw: str) -> str:
    text = _decode_quoted_printable(raw)

    # Keep only the text before the earliest quoted-history marker.
    cut = min((m.start() for m in (r.search(text) for r in _HISTORY_MARKERS) if m), default=len(text))
    text = text[:cut]

    text = _QUOTED_LINE.sub("", text)
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_LINES.sub("\n\n", text)
    return text.strip()
