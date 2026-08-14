"""Gemini embedding generation with manual L2 normalization."""

import asyncio

import httpx
import numpy as np
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.core.constants import EMBEDDING_DIM, EMBEDDING_MODEL


class EmbeddingError(RuntimeError):
    """Raised when the embeddings API cannot be reached."""


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # never divide by zero on an all-zero vector
    return vectors / norms


def _embed_sync(texts: list[str]) -> list[list[float]]:
    client = genai.Client(api_key=get_settings().gemini_api_key)
    try:
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
    except httpx.HTTPError as exc:
        raise EmbeddingError(
            "could not reach the Gemini embeddings API - check connectivity "
            "(generativelanguage.googleapis.com must resolve to a real IP, not 127.0.0.1) "
            "and that GEMINI_API_KEY is set"
        ) from exc
    raw = np.array([e.values for e in result.embeddings], dtype=np.float32)
    return _l2_normalize(raw).tolist()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with gemini-embedding-001, L2-normalized to unit length.

    Runs the blocking Gemini call in a thread so a single embedding never stalls the event loop.
    gemini-embedding-001 does NOT auto-normalize at 1536 dims (confirmed against the docs, 2026-07),
    so normalization happens in `_embed_sync`.
    """
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)
