"""Counting, chunking and learning work for Chinese and Malay as they do for English.

Chinese has no spaces, so `split()` called a whole policy one word: it became one huge chunk, and
every Chinese reply counted as short. Habits were learned across languages, so a Malay greeting
could open an English reply.
"""

from app.core.language import Language, word_count
from app.rag.chunk import TARGET_WORDS, chunk_sections, chunk_text
from app.writing_style import (
    HabitKind,
    ReplyLength,
    _whole_lines,
    clip,
    learn,
    length_of,
)

CHINESE_SENTENCE = "员工须在三十天内提交差旅报销申请。"  # 16 characters and a full stop


def test_chinese_is_counted_in_words_not_in_spaces():
    assert word_count(CHINESE_SENTENCE) == 11  # ceil(16 / 1.5)
    assert word_count("Claims are paid within 30 days.") == 6
    assert word_count("请在 Friday 前回复。") == 1 + 4


def test_a_long_chinese_policy_is_split_into_chunks_on_its_own_full_stops():
    chunks = chunk_text(CHINESE_SENTENCE * 100)
    assert len(chunks) > 1
    assert all(chunk.endswith("。") for chunk in chunks)
    assert all(word_count(chunk) <= TARGET_WORDS for chunk in chunks)


def test_a_numbered_chinese_heading_starts_a_section():
    [piece] = chunk_sections(f"6. 差旅报销\n{CHINESE_SENTENCE}")
    assert piece.section == "6. 差旅报销"


def test_a_long_chinese_reply_is_long():
    assert length_of(CHINESE_SENTENCE * 15) == ReplyLength.LONG


def _greetings(pairs) -> set[tuple[str, Language]]:
    return {(h.value, h.language) for h in learn(pairs) if h.kind == HabitKind.GREETING}


def test_habits_are_learned_per_language():
    english = ("", "Hi there,\n\nThe claim will be paid this week.", 1.0)
    malay = ("", "Salam,\n\nTuntutan anda akan dibayar minggu ini dan saya akan maklumkan.", 1.0)
    assert _greetings([english] * 3 + [malay] * 3) == {("Hi there,", Language.EN), ("Salam,", Language.MS)}


def test_evidence_is_counted_within_one_language():
    english = ("", "Hi there,\n\nThe claim will be paid this week.", 1.0)
    malay = ("", "Hi there,\n\nTuntutan anda akan dibayar minggu ini dan saya akan maklumkan.", 1.0)
    assert _greetings([english] * 2 + [malay] * 2) == set()


def test_the_style_hint_keeps_only_whole_lines():
    assert _whole_lines(["Brief and warm.", "Opens with \"Hi\"."], 20) == "Brief and warm."


def test_a_clipped_example_ends_on_a_whole_word():
    assert clip("Thanks for the update on the invoice", 20) == "Thanks for the"
    assert clip("short", 20) == "short"
