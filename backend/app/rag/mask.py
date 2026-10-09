"""Text masked before storage and embedding, the promise email content gets.

Fails closed like the listener: if Presidio cannot be reached the text is refused, never stored unmasked.
Each kind of content has a named profile. A policy keeps locations and organisations (an office address
in a policy is not personal, and masking it would hurt retrieval). The user's own reply is masked like
an email (the listener's entities and its context-gated account numbers).
"""

from enum import StrEnum

import httpx

from app.core.config import get_settings
from app.core.typed_text import mask_typed_text


class MaskProfile(StrEnum):
    POLICY = "policy"  # uploaded and pasted documents
    PERSONAL = "personal"  # the user's own replies: style examples, past replies


_ENTITIES = {
    MaskProfile.POLICY: ["PERSON", "CREDIT_CARD", "IBAN_CODE", "PHONE_NUMBER"],
    # The listener's set (listener/main.go), so a reply is masked as strictly as the email it answers.
    MaskProfile.PERSONAL: ["PERSON", "LOCATION", "ORGANIZATION", "ACCOUNT_NUMBER", "CREDIT_CARD", "IBAN_CODE",
                           "PHONE_NUMBER", "EMAIL_ADDRESS"],
}
# The listener's context-gated account recogniser: a bare digit run is an account only near these words.
_ACCOUNT_RECOGNIZER = {
    "name": "FLEXIBLE_ACCOUNT_RECOGNIZER", "supported_language": "en", "supported_entity": "ACCOUNT_NUMBER",
    "patterns": [{"name": "arbitrary_digit_pattern", "regex": r"\b\d{4,16}\b", "score": 0.4}],
    "context": ["account", "acc", "bank", "maybank", "cimb", "rhb", "public bank", "transfer", "reference", "ref",
                "passport", "policy", "member", "employee", "emp", "staff", "badge", "payroll"],
}
_SCORE_THRESHOLD = 0.6
_CHUNK_CHARS = 3_000  # the listener's NER chunk size; Presidio slows sharply on long texts
_TIMEOUT_SECONDS = 15.0
_MASK = "[Redacted]"


class DocumentMaskingError(RuntimeError):
    """Presidio could not be reached, so the document was not stored."""


def _chunks(text: str) -> list[str]:
    """Split at whitespace so a name is never cut in half between two analyzer calls."""
    pieces: list[str] = []
    while len(text) > _CHUNK_CHARS:
        cut = text.rfind(" ", 0, _CHUNK_CHARS)
        cut = cut if cut > 0 else _CHUNK_CHARS
        pieces.append(text[:cut])
        text = text[cut:]
    return [*pieces, text]


def _replace_spans(text: str, hits: list[dict]) -> str:
    """Replace each detected span, last first, so earlier offsets stay valid."""
    for hit in sorted(hits, key=lambda h: h["start"], reverse=True):
        text = text[: hit["start"]] + _MASK + text[hit["end"] :]
    return text


def _request(text: str, profile: MaskProfile) -> dict:
    body = {"text": text, "language": "en", "entities": _ENTITIES[profile], "score_threshold": _SCORE_THRESHOLD}
    return body | {"ad_hoc_recognizers": [_ACCOUNT_RECOGNIZER]} if profile == MaskProfile.PERSONAL else body


async def _mask_names(client: httpx.AsyncClient, url: str, text: str, profile: MaskProfile) -> str:
    response = await client.post(url, json=_request(text, profile))
    response.raise_for_status()
    return _replace_spans(text, response.json())


async def mask_document(text: str, *, profile: MaskProfile) -> str:
    """The text with fixed formats and the profile's detected entities redacted."""
    floor = mask_typed_text(text, preserve_business_emails=(profile == MaskProfile.POLICY))
    url = get_settings().presidio_analyzer_url
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            return "".join([await _mask_names(client, url, piece, profile) for piece in _chunks(floor)])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise DocumentMaskingError(str(exc)) from exc
