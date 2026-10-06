"""The marks masking leaves in stored text, shared by the agent, the send path and the vault.

Two families. Fixed markers can never be filled back in: the listener's old regex tokens
([EMAIL_REDACTED]), Presidio's old replacement ([Redacted]) and the OCR transcription ([REDACTED]).
Numbered placeholders ([PERSON_1]) stand for a detail kept in the email's encrypted vault and are
filled in at send time (specs/features/restorable-masking.md).
"""

import re

# The parenthesised two are the writing style's (app/writing_style.py): copied from an example.
REDACTION_MARKER = re.compile(r"\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]|\((?:hidden|name)\)")

DETAIL_KINDS = ("PERSON", "EMAIL", "PHONE", "IC", "PASSPORT", "ACCOUNT", "CARD", "LOCATION", "ORG")
PLACEHOLDER = re.compile(r"\[(" + "|".join(DETAIL_KINDS) + r")_(\d+)\]")
# Either family: what a translation must carry over unchanged.
ANY_MASK = re.compile(f"{REDACTION_MARKER.pattern}|{PLACEHOLDER.pattern}")


def has_redaction_marker(text: str) -> bool:
    """A fixed marker, which would reach a recipient exactly as written."""
    return bool(REDACTION_MARKER.search(text))
