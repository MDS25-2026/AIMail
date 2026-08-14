"""Retrieval evaluation metrics for the RAG harness (S4).

Relevance is judged by content markers (hand-labelled substrings), not chunk IDs:
IDs are random UUIDs assigned at ingest and cannot be labelled ahead of time. A
retrieved chunk counts as relevant if it contains any of a query's marker strings.
"""

from app.rag.retrieve import ContextChunk


def relevance_judgments(chunks: list[ContextChunk], markers: list[str]) -> list[bool]:
    lowered = [marker.lower() for marker in markers]
    return [any(marker in chunk["content"].lower() for marker in lowered) for chunk in chunks]


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
