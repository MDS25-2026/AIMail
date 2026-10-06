"""Grounded answer generation for the /ask demo.

This closes the RAG loop (retrieve -> generate) for demonstration. Real reply generation
(the Router / Drafter / Critic pipeline) is Lane C's job; this is a thin, clearly-scoped
demo of the loop, not that pipeline.
"""

import asyncio

import httpx
from google import genai

from app.core.config import get_settings
from app.rag.retrieve import ContextChunk

_PROMPT = """You are a company-policy assistant. Answer the question using ONLY the policy \
excerpts below. If the answer is not in the excerpts, say the policy does not cover it. \
Be concise and cite the source titles.

Policy excerpts:
{context}

Question: {question}
Answer:"""


class GenerationError(RuntimeError):
    """Raised when the answer model cannot be reached."""


def _format_context(chunks: list[ContextChunk]) -> str:
    return "\n\n".join(
        f"[{i + 1}] (source: {chunk['source_title']}) {chunk['content']}"
        for i, chunk in enumerate(chunks)
    )


async def answer(question: str, chunks: list[ContextChunk]) -> str:
    if not chunks:
        return "The knowledge base has no policy to answer from yet."
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    prompt = _PROMPT.format(context=_format_context(chunks), question=question)
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_chat_model,
            contents=prompt,
        )
    except httpx.HTTPError as exc:
        raise GenerationError("could not reach the Gemini generation API") from exc
    return response.text or ""
