"""Private mode's embeddings (specs/features/local-model.md): Ollama on the company's own machine.

The same shape as app/rag/embed.py, so retrieval swaps one for the other. A failure raises
EmbeddingError and never falls back to Gemini, which would send the text to Google.
"""

import httpx
import numpy as np

from app.core.config import get_settings
from app.core.providers import Provider
from app.rag.embed import l2_normalize
from app.rag.embedding_models import checked
from app.rag.errors import EmbeddingError

EMBED_PATH = "/api/embed"
EMBED_TIMEOUT_SECONDS = 60
# EmbeddingGemma's own prompts for the two sides of a search; vectors made without them match worse.
QUERY_PREFIX = "task: search result | query: "
DOCUMENT_PREFIX = "title: none | text: "


def local_model() -> str:
    """The configured local embedding model; "" means Private mode has no search."""
    return get_settings().local_embedding_model.strip()


def local_tag() -> str:
    """Stored in local_embedding.model_name, so changing the model re-embeds instead of mixing."""
    return f"{local_model()}/search-prompts"


async def _embed(texts: list[str]) -> list[list[float]]:
    settings = get_settings()
    url = settings.local_llm_url.rstrip("/") + EMBED_PATH
    try:
        async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json={"model": local_model(), "input": texts})
            response.raise_for_status()
        raw = np.array(response.json()["embeddings"], dtype=np.float32)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise EmbeddingError(f"could not reach the local embedding model at {url}") from exc
    return checked(l2_normalize(raw).tolist(), Provider.LOCAL, local_model())


async def embed_documents_locally(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await _embed([DOCUMENT_PREFIX + text for text in texts])


async def embed_query_locally(text: str) -> list[float] | None:
    if not text.strip():
        return None
    vectors = await _embed([QUERY_PREFIX + text])
    return vectors[0] if vectors else None
