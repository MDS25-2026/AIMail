"""Policy-PDF text extraction and sentence-aware chunking."""

import io
import re
from pathlib import Path

from pypdf import PdfReader

# Chunks are packed to a target word count but always end on a sentence boundary, so a chunk
# never cuts mid-sentence. ~1.3 tokens/word (English) maps the spec's 512/128-token target
# onto these word counts; token_count is an estimate.
TARGET_WORDS = 380
OVERLAP_WORDS = 96
TOKENS_PER_WORD = 1.3

# Split on sentence punctuation followed by a capital, so a period inside a number ("1.75",
# "30 days.") does not trigger a split (it is not followed by whitespace + a capital).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _extract(reader: PdfReader) -> str:
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages).strip()


def extract_pdf_text(path: Path) -> str:
    return _extract(PdfReader(path))


def extract_pdf_bytes(data: bytes) -> str:
    return _extract(PdfReader(io.BytesIO(data)))


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [s.strip() for s in _SENTENCE_BOUNDARY.split(normalized) if s.strip()]


def _overlap_tail(sentences: list[str]) -> tuple[list[str], int]:
    tail: list[str] = []
    words = 0
    for sentence in reversed(sentences):
        count = len(sentence.split())
        if tail and words + count > OVERLAP_WORDS:
            break
        tail.insert(0, sentence)
        words += count
    return tail, words


def chunk_text(text: str) -> list[str]:
    sentences = _sentences(text)
    if not sentences:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        count = len(sentence.split())
        if current and current_words + count > TARGET_WORDS:
            chunks.append(" ".join(current))
            current, current_words = _overlap_tail(current)
        current.append(sentence)
        current_words += count
    chunks.append(" ".join(current))
    return chunks


def estimate_tokens(chunk: str) -> int:
    return round(len(chunk.split()) * TOKENS_PER_WORD)
