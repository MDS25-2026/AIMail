"""The one way text reaches a model, in the backend and the agent (specs/context/backbone-contracts.md).

Callers name the provider explicitly (there is no default to fall back on), and the gateway routes to
Gemini or the company's local model. Before anything leaves, the fixed-format floor (emails, phones, IC and
card numbers) runs over the whole prompt as a last net: a detail that slipped past masking upstream is
masked here and logged, never sent. Every call is recorded as an egress record: what went where, how long,
and how many details of each kind were hidden, so the privacy receipt can show a record, not a claim.
"""

import hashlib
import logging
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field

from app.core.providers import Provider
from app.core.redaction import PLACEHOLDER, REDACTION_MARKER
from app.core.typed_text import mask_typed_text
from app.rag.embed import embed_documents as gemini_embed_documents
from app.rag.embed import embed_query as gemini_embed_query
from app.rag.local_embed import embed_documents_locally, embed_query_locally
from gemini_client import generate as gemini_generate
from local_client import generate_local

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Egress:
    """One prompt that left for a model. No text is kept: its length, digest and hidden-detail counts."""

    purpose: str
    provider: str
    chars: int
    sha256: str
    hidden: dict[str, int] = field(default_factory=dict)
    # Details the last net caught: should always be 0; anything else is a masking bug upstream.
    caught: int = 0


_egress: ContextVar[list[Egress] | None] = ContextVar("egress", default=None)


@contextmanager
def track_egress() -> Iterator[list[dict]]:
    """Collect every prompt sent inside the block, as JSON-ready dicts once it exits."""
    sent: list[Egress] = []
    report: list[dict] = []
    token = _egress.set(sent)
    try:
        yield report
    finally:
        _egress.reset(token)
        report.extend(asdict(record) for record in sent)


def last_net(text: str) -> tuple[str, int]:
    """The text with any fixed-format detail masked, and how many there were."""
    masked = mask_typed_text(text)
    caught = len(REDACTION_MARKER.findall(masked)) - len(REDACTION_MARKER.findall(text))
    if caught:
        logger.warning("%d fixed-format detail(s) reached the model gateway unmasked; masked before sending", caught)
    return masked, caught


def _note(purpose: str, provider: Provider, prompt: str, caught: int) -> None:
    sent = _egress.get()
    if sent is None:
        return
    hidden = Counter(match.group(1).lower() for match in PLACEHOLDER.finditer(prompt))
    sent.append(Egress(purpose, provider.value, len(prompt), hashlib.sha256(prompt.encode()).hexdigest(),
                       dict(hidden), caught))


async def generate(prompt: str, *, provider: Provider, purpose: str, system: str | None = None,
                   response_schema: dict | None = None, max_output_tokens: int | None = None) -> dict | str:
    """Parsed JSON when a schema is given. Raises ModelError (model_runtime) on any failure."""
    safe_prompt, caught = last_net(prompt)
    safe_system = last_net(system)[0] if system else None
    _note(purpose, provider, safe_prompt, caught)
    answer = generate_local if provider == Provider.LOCAL else gemini_generate
    return await answer(safe_prompt, response_schema=response_schema, max_output_tokens=max_output_tokens,
                        system=safe_system)


async def embed_documents(texts: list[str], *, provider: Provider, purpose: str) -> list[list[float]]:
    """Vectors for stored chunks; the same last net and record as generation."""
    safe = [_checked(text, provider, purpose) for text in texts]
    return await (embed_documents_locally(safe) if provider == Provider.LOCAL else gemini_embed_documents(safe))


async def embed_query(text: str, *, provider: Provider, purpose: str) -> list[float] | None:
    """The vector a search compares against stored chunks, or None for empty input."""
    safe = _checked(text, provider, purpose)
    return await (embed_query_locally(safe) if provider == Provider.LOCAL else gemini_embed_query(safe))


def _checked(text: str, provider: Provider, purpose: str) -> str:
    safe, caught = last_net(text)
    _note(purpose, provider, safe, caught)
    return safe
