from app.rag.chunk import OVERLAP_WORDS, TARGET_WORDS, chunk_text, estimate_tokens


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
