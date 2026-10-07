"""Policy-PDF text extraction and sentence-aware chunking."""

import io
import re
from dataclasses import dataclass
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
# One space, not \s+: _sentences collapses whitespace first, and a fixed width leaves nothing to
# backtrack over, so no input can make the split slow (CodeQL py/polynomial-redos).
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?]) (?=[A-Z])")


# A section heading (specs/features/rag-retrieval.md): "6. Travel claims", "6.2 Late claims". The dot
# keeps a page footer ("21 April 2025") out; two digits at most keep a wrapped year ("2026. Self-...") out.
_SECTION_HEADING = re.compile(r"\d{1,2}(?:\.\d{1,2})*\. *[A-Z].*|\d{1,2}(?:\.\d{1,2})+ +[A-Z].*")
# A contents page lists every heading with dot leaders to a page number; those lines are not sections.
_DOT_LEADER = ".."
_SENTENCE_END = (".", "!", "?", ":", ";", ",")
MAX_HEADING_WORDS = 12
# Where a chunk's heading is kept in chunk.metadata.
SECTION_KEY = "section"


@dataclass(frozen=True)
class Piece:
    """One chunk to store, with the heading of the section it came from, if the document has any."""

    content: str
    section: str | None = None


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


def _is_heading(line: str) -> bool:
    return (bool(_SECTION_HEADING.fullmatch(line)) and len(line.split()) <= MAX_HEADING_WORDS
            and not line.endswith(_SENTENCE_END) and _DOT_LEADER not in line)


def _sections(text: str) -> list[tuple[str | None, str]]:
    """(heading, body) pairs in order; text before the first heading has no heading."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for line in text.splitlines():
        stripped = line.strip()
        if _is_heading(stripped):
            sections.append((stripped, []))
        else:
            sections[-1][1].append(line)
    return [(heading, "\n".join(body)) for heading, body in sections]


def chunk_sections(text: str) -> list[Piece]:
    """Chunks that never cross a section, each led by its heading so the vector knows the topic."""
    return [
        Piece(f"{heading}\n{chunk}" if heading else chunk, heading)
        for heading, body in _sections(text)
        for chunk in chunk_text(body)
    ]


def estimate_tokens(chunk: str) -> int:
    return round(len(chunk.split()) * TOKENS_PER_WORD)
