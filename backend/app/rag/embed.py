"""Gemini embedding generation with manual L2 normalization."""

import asyncio

import httpx
import numpy as np
from google.genai import errors, types

from app.core.constants import EMBEDDING_DIM, EMBEDDING_MODEL
from app.rag.gemini import gemini_client


class EmbeddingError(RuntimeError):
    """Raised when the embeddings API cannot be reached."""


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # never divide by zero on an all-zero vector
    return vectors / norms


# Gemini tunes the vector for its role: a policy chunk and a question about it land closer
# together when each is embedded for its own side of retrieval.
DOCUMENT_TASK = "RETRIEVAL_DOCUMENT"
QUERY_TASK = "RETRIEVAL_QUERY"


def _embed_sync(texts: list[str], task_type: str) -> list[list[float]]:
    client = gemini_client()
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(
                output_dimensionality=EMBEDDING_DIM, task_type=task_type
            ),
        )
    except (httpx.HTTPError, errors.APIError) as exc:
        raise EmbeddingError(
            "could not reach the Gemini embeddings API - check connectivity "
            "(generativelanguage.googleapis.com must resolve to a real IP, not 127.0.0.1) "
            "and that GOOGLE_API_KEY is set"
        ) from exc
    raw = np.array([e.values for e in result.embeddings], dtype=np.float32)
    return _l2_normalize(raw).tolist()


async def _embed(texts: list[str], task_type: str) -> list[list[float]]:
    """Embed with gemini-embedding-001, L2-normalized to unit length.

    Runs the blocking Gemini call in a thread so a single embedding never stalls the event loop.
    gemini-embedding-001 does NOT auto-normalize at 1536 dims (confirmed against the docs, 2026-07),
    so normalization happens in `_embed_sync`.
    """
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts, task_type)


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Vectors for stored policy chunks."""
    return await _embed(texts, DOCUMENT_TASK)


async def embed_query(text: str) -> list[float] | None:
    """The vector a search compares against stored chunks, or None for empty input."""
    if not text.strip():
        return None  # an empty body has nothing to search for, and the API rejects it
    vectors = await _embed([text], QUERY_TASK)
    return vectors[0] if vectors else None
