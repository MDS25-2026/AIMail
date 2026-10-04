"""Uploaded documents are masked before storage and embedding, the promise email content gets.

Fails closed like the listener: if Presidio cannot be reached the document is refused, never stored
unmasked. Locations are kept on purpose: an office address in a policy is not personal, and masking
it would hurt retrieval.
"""

import httpx

from app.core.config import get_settings
from app.core.typed_text import mask_typed_text

_ENTITIES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE"]
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


async def _mask_names(client: httpx.AsyncClient, url: str, text: str) -> str:
    response = await client.post(url, json={
        "text": text, "language": "en", "entities": _ENTITIES, "score_threshold": _SCORE_THRESHOLD,
    })
    response.raise_for_status()
    return _replace_spans(text, response.json())


async def mask_document(text: str) -> str:
    """The document with fixed formats and detected names, emails, phones and accounts redacted."""
    floor = mask_typed_text(text)
    url = get_settings().presidio_analyzer_url
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            return "".join([await _mask_names(client, url, piece) for piece in _chunks(floor)])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise DocumentMaskingError(str(exc)) from exc
