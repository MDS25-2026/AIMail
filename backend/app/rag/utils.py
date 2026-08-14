"""Retrieval helpers — formatting retrieved chunks for downstream lanes."""

from app.contracts import ContextChunk


def format_rag_context(chunks: list[ContextChunk]) -> str:
    """Format retrieved chunks into the plain-text ``rag_context`` string Lane C's /process-email
    expects. Each chunk becomes ``[source_title] content``, joined by blank lines. An empty list
    yields an empty string (Lane C then degrades to no-policy-grounding).
    """
    return "\n\n".join(f"[{chunk['source_title']}] {chunk['content']}" for chunk in chunks)
