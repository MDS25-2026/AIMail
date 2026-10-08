"""Grounded answer generation for the /ask demo.

This closes the RAG loop (retrieve -> generate) for demonstration. Real reply generation
(the Router / Drafter / Critic pipeline) is Lane C's job; this is a thin, clearly-scoped
demo of the loop, not that pipeline.
"""

import model_gateway
from app.core.providers import Provider
from app.rag.retrieve import ContextChunk

ASK = "ask"  # the egress purpose
ANSWER_MAX_TOKENS = 1024

_PROMPT = """You are a company-policy assistant. Answer the question using ONLY the policy \
excerpts below. If the answer is not in the excerpts, say the policy does not cover it. \
Be concise and cite the source titles.

Policy excerpts:
{context}

Question: {question}
Answer:"""


def _format_context(chunks: list[ContextChunk]) -> str:
    return "\n\n".join(
        f"[{i + 1}] (source: {chunk['source_title']}) {chunk['content']}"
        for i, chunk in enumerate(chunks)
    )


async def answer(question: str, chunks: list[ContextChunk], *, provider: Provider) -> str:
    """Raises ModelError when the model cannot answer; the API turns it into a 503."""
    if not chunks:
        return "The knowledge base has no policy to answer from yet."
    prompt = _PROMPT.format(context=_format_context(chunks), question=question)
    reply = await model_gateway.generate(prompt, provider=provider, purpose=ASK, max_output_tokens=ANSWER_MAX_TOKENS)
    return reply if isinstance(reply, str) else ""
