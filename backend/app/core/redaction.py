"""The redaction markers masking leaves in stored text, shared by the agent and the send path."""

import re

# Three shapes reach stored text: the listener's regex tokens ([EMAIL_REDACTED]), Presidio's
# replacement ([Redacted], listener/main.go) and the OCR transcription ([REDACTED], listener/ocr.go).
REDACTION_MARKER = re.compile(r"\[(?:[A-Z_]+_REDACTED|Redacted|REDACTED)\]")


def has_redaction_marker(text: str) -> bool:
    return bool(REDACTION_MARKER.search(text))
