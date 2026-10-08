"""Choosing the retrieval cutoff from labelled questions (eval/retrieval), the same way every time.

A search returns its top k chunks, best first. The cutoff keeps the ones scoring at least
`cutoff` times the best score (retrieve.close_to_best). Too low and unrelated policy reaches the
draft; too high and a second relevant section is lost. The chosen value is the one with the best
mean F1 over the questions, where a kept chunk is right when it comes from a section that answers
the question. Recall counts only relevant chunks within the top k: the cutoff cannot find more.
"""

from dataclasses import dataclass

# 0.50 to 1.00 in steps of 0.01.
GRID = tuple(round(0.5 + step / 100, 2) for step in range(51))
# F1 differences below this are measurement noise; ties go to the lower cutoff, which keeps more.
F1_PRECISION = 6


@dataclass(frozen=True)
class Ranked:
    """One question's search result: scores best first, and which chunks answer it."""

    query_id: str
    language: str
    scores: list[float]
    relevant: list[bool]


def kept(result: Ranked, cutoff: float) -> list[bool]:
    floor = result.scores[0] * cutoff if result.scores else 0.0
    return [score >= floor for score in result.scores]


def f1(result: Ranked, cutoff: float) -> float:
    keep = kept(result, cutoff)
    right = sum(is_kept and is_relevant for is_kept, is_relevant in zip(keep, result.relevant, strict=True))
    if right == 0:
        return 0.0
    precision, recall = right / sum(keep), right / sum(result.relevant)
    return 2 * precision * recall / (precision + recall)


def mean_f1(results: list[Ranked], cutoff: float) -> float:
    return sum(f1(result, cutoff) for result in results) / len(results) if results else 0.0


def hit_rate(results: list[Ranked], cutoff: float) -> float:
    """Share of questions where at least one kept chunk answers them."""
    hits = sum(any(k and r for k, r in zip(kept(result, cutoff), result.relevant, strict=True))
               for result in results)
    return hits / len(results) if results else 0.0


def best_cutoff(results: list[Ranked]) -> float:
    return max(GRID, key=lambda cutoff: (round(mean_f1(results, cutoff), F1_PRECISION), -cutoff))
