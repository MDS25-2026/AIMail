"""Load and split a labelled email dataset for the classifier.

Expects a CSV with a text column and a label column (defaults `text` / `label`). Column names
are overridable so a public set (e.g. the spam corpus) works without renaming.
"""

import csv
from pathlib import Path

from sklearn.model_selection import train_test_split

_TEST_SIZE = 0.2
_SEED = 42


def load_dataset(
    path: Path, text_col: str = "text", label_col: str = "label"
) -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            text = (row.get(text_col) or "").strip()
            label = (row.get(label_col) or "").strip()
            if text and label:
                texts.append(text)
                labels.append(label)
    return texts, labels


def stratified_split(
    texts: list[str], labels: list[str], test_size: float = _TEST_SIZE, seed: int = _SEED
) -> tuple[list[str], list[str], list[str], list[str]]:
    """Train/test split that preserves class balance across both sides."""
    return train_test_split(texts, labels, test_size=test_size, stratify=labels, random_state=seed)
