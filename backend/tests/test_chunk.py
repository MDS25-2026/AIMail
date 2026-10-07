import pytest

from app.rag import retrieve
from app.rag.chunk import (
    OVERLAP_WORDS,
    TARGET_WORDS,
    Piece,
    chunk_sections,
    chunk_text,
    estimate_tokens,
)
from app.rag.retrieve import close_to_best


def test_empty_or_whitespace_text_produces_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n  ") == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("Employees may work remotely.") == ["Employees may work remotely."]


def test_chunks_end_on_sentence_boundaries_never_mid_sentence():
    text = " ".join(f"Clause {i} states a distinct policy point clearly." for i in range(200))
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(chunk.rstrip().endswith(".") for chunk in chunks)


def test_no_chunk_exceeds_the_target_word_count():
    text = " ".join(f"Rule {i} describes an obligation in some detail." for i in range(200))
    assert all(len(chunk.split()) <= TARGET_WORDS for chunk in chunk_text(text))


def test_consecutive_chunks_overlap():
    text = " ".join(f"Point {i} is a clear and distinct policy statement." for i in range(300))
    chunks = chunk_text(text)
    assert len(chunks) >= 2
    end_of_first = set(chunks[0].split()[-OVERLAP_WORDS:])
    start_of_second = set(chunks[1].split()[:OVERLAP_WORDS])
    assert end_of_first & start_of_second


def test_a_period_inside_a_number_does_not_split_the_sentence():
    chunks = chunk_text("Leave accrues at 1.75 days per month up to 10 days.")
    assert chunks == ["Leave accrues at 1.75 days per month up to 10 days."]


def test_token_estimate_scales_with_word_count():
    assert estimate_tokens("one two three four") == round(4 * 1.3)


# ---------- sections (specs/features/rag-retrieval.md) ----------

HANDBOOK = """Lumora Works Employee Handbook
Version 2.1. Effective 1 January 2026.
5. Remote work policy
Employees may work remotely up to 3 days per week.
6. Travel and expense claims policy
Expense claims must be submitted within 30 days.
6.2 Late claims
A late claim needs written approval."""


def test_no_chunk_mixes_two_sections_and_each_names_its_heading():
    pieces = chunk_sections(HANDBOOK)
    assert [piece.section for piece in pieces] == [
        None, "5. Remote work policy", "6. Travel and expense claims policy", "6.2 Late claims"]
    assert pieces[1].content == "5. Remote work policy\nEmployees may work remotely up to 3 days per week."
    assert "30 days" not in pieces[1].content


def test_a_document_without_numbered_headings_is_chunked_as_before():
    text = "Employees may work remotely. Claims are due within 30 days."
    assert chunk_sections(text) == [Piece(chunk) for chunk in chunk_text(text)]


@pytest.mark.parametrize("line", [
    "3.0 Amendments to the Code .......................................... 24",  # a contents page
    "21 April 2025",  # a page footer
    "2026. Self-assessments are due by 13 November 2026",  # a wrapped sentence starting with a year
    "7 calendar days in advance through the HR Portal",
    "1. Submit the form before the 20th of the month.",  # a numbered step, not a heading
])
def test_lines_that_only_look_like_headings_do_not_split_a_section(line):
    pieces = chunk_sections(f"5. Remote work policy\nEmployees may work remotely.\n{line}\nMore text follows here.")
    assert [piece.section for piece in pieces] == ["5. Remote work policy"]


def _hit(score: float) -> dict:
    return {"chunk_id": None, "content": "", "similarity_score": score, "source_title": ""}


def test_hits_well_below_the_best_one_are_dropped():
    kept = close_to_best([_hit(0.41), _hit(0.38), _hit(0.27), _hit(0.22)], 0.85)
    assert [hit["similarity_score"] for hit in kept] == [0.41, 0.38]


def test_no_hits_stay_no_hits():
    assert close_to_best([], 0.85) == []


def test_a_source_is_labelled_with_its_section_when_it_has_one():
    assert retrieve._label("Handbook.pdf", "6. Travel and expense claims policy") == (
        "Handbook.pdf · 6. Travel and expense claims policy")
    assert retrieve._label("Handbook.pdf", None) == "Handbook.pdf"
