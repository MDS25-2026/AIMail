"""Retrieval evaluation metrics for the RAG harness (S4).

Relevance is judged by the section a chunk came from (eval/retrieval/v1 onward) or, for the
older v0 set, by content markers (hand-labelled substrings). Never by chunk IDs: those are
random UUIDs assigned at ingest and cannot be labelled ahead of time.
"""

from app.rag.retrieve import SECTION_SEPARATOR, ContextChunk


def relevance_judgments(chunks: list[ContextChunk], markers: list[str]) -> list[bool]:
    lowered = [marker.lower() for marker in markers]
    return [any(marker in chunk["content"].lower() for marker in lowered) for chunk in chunks]


def section_judgments(chunks: list[ContextChunk], sections: list[str]) -> list[bool]:
    """Relevant when the chunk comes from one of the sections that answer the question."""
    endings = tuple(f"{SECTION_SEPARATOR}{section}" for section in sections)
    return [chunk["source_title"].endswith(endings) for chunk in chunks]


def precision_at_k(judgments: list[bool]) -> float:
    if not judgments:
        return 0.0
    return sum(judgments) / len(judgments)


def reciprocal_rank(judgments: list[bool]) -> float:
    for rank, is_relevant in enumerate(judgments, start=1):
        if is_relevant:
            return 1.0 / rank
    return 0.0


def hit_rate(judgments: list[bool]) -> bool:
    return any(judgments)
