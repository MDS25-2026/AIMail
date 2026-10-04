"""Query reformulation (R03.1).

Rewrites a user's natural question into policy-style search terms before embedding, to lift
retrieval of passages that use formal or different wording. Measured against the raw-query
baseline by the eval harness (S4). Falls back to the raw question if the model call fails, so
reformulation can never make retrieval worse than the baseline by erroring.
"""

import asyncio

import httpx
from google.genai import errors

from app.core.config import get_settings
from app.rag.gemini import gemini_client

_PROMPT = """Rewrite the user's question into a concise search query that matches formal
company-policy wording. Expand it with likely synonyms and policy terms (e.g. "relatives" ->
"related persons, family, spouse"). Keep it under 30 words. Output only the rewritten query.

Question: {question}
Search query:"""


async def reformulate(question: str) -> str:
    settings = get_settings()
    client = gemini_client()
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=settings.gemini_chat_model,
            contents=_PROMPT.format(question=question),
        )
    except (httpx.HTTPError, errors.APIError):
        return question
    return (response.text or question).strip()
