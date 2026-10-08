"""Query reformulation (R03.1).

Rewrites a user's natural question into policy-style search terms before embedding, to lift
retrieval of passages that use formal or different wording. Measured against the raw-query
baseline by the eval harness (S4). Falls back to the raw question if the model call fails, so
reformulation can never make retrieval worse than the baseline by erroring.
"""

import model_gateway
from app.core.providers import Provider
from model_runtime import ModelError

REFORMULATE = "reformulate"  # the egress purpose
REFORMULATE_MAX_TOKENS = 128

_PROMPT = """Rewrite the user's question into a concise search query that matches formal
company-policy wording. Expand it with likely synonyms and policy terms (e.g. "relatives" ->
"related persons, family, spouse"). Keep it under 30 words. Output only the rewritten query.

Question: {question}
Search query:"""


async def reformulate(question: str, *, provider: Provider) -> str:
    try:
        reply = await model_gateway.generate(_PROMPT.format(question=question), provider=provider,
                                             purpose=REFORMULATE, max_output_tokens=REFORMULATE_MAX_TOKENS)
    except ModelError:
        return question
    return reply.strip() if isinstance(reply, str) and reply.strip() else question
