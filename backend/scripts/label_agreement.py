"""Measure agreement between the human labels and the Gemini labels on the same emails.

The key diagnostic: if the model trained on Gemini labels only reaches ~0.57 against human labels,
how much do the two label sources even agree? Low agreement means label quality — not model
capacity — is the ceiling. Reports overall agreement, Cohen's kappa, per-class agreement, and a
confusion matrix of human (rows) vs Gemini (cols).

Usage (from backend/):
    python scripts/label_agreement.py enron_train_human.csv enron_gemini_labels.csv
"""

import argparse
import csv
from pathlib import Path

from sklearn.metrics import cohen_kappa_score, confusion_matrix

csv.field_size_limit(10**9)
_LABELS = ["low", "medium", "high"]


def _load(path: Path, label_col: str) -> dict[str, str]:
    rows = csv.DictReader(path.open(encoding="utf-8"))
    return {r["text"]: r[label_col].strip().lower() for r in rows if r[label_col].strip()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("human", help="CSV with text + label (human labels)")
    parser.add_argument("gemini", help="CSV with text + gemini_label")
    args = parser.parse_args()

    human = _load(Path(args.human), "label")
    gemini = _load(Path(args.gemini), "gemini_label")
    shared = [t for t in human if t in gemini and human[t] in _LABELS and gemini[t] in _LABELS]
    h = [human[t] for t in shared]
    g = [gemini[t] for t in shared]

    agree = sum(1 for a, b in zip(h, g) if a == b)
    print(f"emails compared: {len(shared)}")
    print(f"overall agreement: {agree}/{len(shared)} ({100 * agree / len(shared):.1f}%)")
    print(f"Cohen's kappa: {cohen_kappa_score(h, g):.3f}  (0=chance, 1=perfect; <0.4 = poor)\n")

    for label in _LABELS:
        idx = [i for i, x in enumerate(h) if x == label]
        same = sum(1 for i in idx if g[i] == label)
        print(f"  human '{label}' ({len(idx)}): Gemini agreed on {same} ({100 * same / max(len(idx), 1):.0f}%)")

    print("\nconfusion (rows=human, cols=Gemini; order low/medium/high):")
    for label, row in zip(_LABELS, confusion_matrix(h, g, labels=_LABELS)):
        print(f"  {label:7} {row}")


if __name__ == "__main__":
    main()
