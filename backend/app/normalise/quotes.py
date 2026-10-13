"""Where a reply's quoted email begins (specs/features/normalisation-v2.md).

The same lines listener/sla.go and the dashboard's src/lib/quotedText.ts cut at: "> " lines, the header a
mail client writes above a quote, and Outlook's From/Sent block, in English, Malay and Chinese.
"""

import re

_QUOTE_START = re.compile(
    r"^(?:>|-{2,}\s*Original Message|From:\s|Sent:\s|On .*wrote:\s*$|Pada .*(?:menulis|tulis):\s*$|.*写道[:：]\s*$)",
    re.IGNORECASE,
)
# A client may wrap "On Tue, 7 Oct 2026, Aisyah <a@b.c>" and "wrote:" over two lines.
_WRAPPED_HEADER_START = re.compile(r"^(?:On|Pada)\s", re.IGNORECASE)
_HEADER_END = re.compile(r"(?:wrote|menulis|tulis):\s*$|写道[:：]\s*$", re.IGNORECASE)


def own_text(body: str) -> str:
    """What the sender wrote, without the email quoted beneath it."""
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if _QUOTE_START.match(line.strip()):
            return "\n".join(lines[:index])
        is_wrapped_header = (_HEADER_END.search(line.strip()) and index > 0
                             and _WRAPPED_HEADER_START.match(lines[index - 1].strip()))
        if is_wrapped_header:
            return "\n".join(lines[:index - 1])
    return body
