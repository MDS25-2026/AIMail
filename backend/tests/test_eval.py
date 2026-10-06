from app.rag.eval import hit_rate, precision_at_k, reciprocal_rank, relevance_judgments


def _chunk(content: str):
    return {"chunk_id": None, "content": content, "similarity_score": 1.0, "source_title": "t"}


def test_relevance_judgments_match_markers_case_insensitively():
    chunks = [_chunk("Travel reimbursement within 30 DAYS"), _chunk("unrelated text")]
    assert relevance_judgments(chunks, ["30 days"]) == [True, False]


def test_precision_at_k_is_fraction_relevant():
    assert precision_at_k([True, False, True, False]) == 0.5
    assert precision_at_k([]) == 0.0


def test_reciprocal_rank_uses_first_hit_only():
    assert reciprocal_rank([False, False, True]) == 1 / 3
    assert reciprocal_rank([False, False]) == 0.0


def test_hit_rate_is_any_relevant():
    assert hit_rate([False, True]) is True
    assert hit_rate([False, False]) is False
