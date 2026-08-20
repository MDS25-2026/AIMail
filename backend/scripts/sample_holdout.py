"""Pull an unlabeled holdout sample from the Enron corpus for YOU to hand-label.

This is the human-labeled test set that keeps evaluation honest: train on the Gemini-labeled data
(label_dataset.py), measure accuracy on this. It is disjoint from the training sample by
construction (training takes every 300th email from offset 0; this takes offset 150), so there is
no leakage. Output has a blank `label` column — fill each row with low / medium / high by hand,
using the same rubric.

Usage (from backend/):
    python scripts/sample_holdout.py <emails.csv | archive.zip> --limit 120 --out holdout.csv
"""

import argparse
import csv
from pathlib import Path

from label_dataset import _parse, _rows  # reuse the corpus reader + RFC-822 parser


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="emails.csv or archive.zip")
    parser.add_argument("--limit", type=int, default=120)
    parser.add_argument("--out", default="holdout.csv")
    args = parser.parse_args()

    parsed = (t for t in (_parse(m) for m in _rows(Path(args.source))) if t)
    rows: list[str] = []
    for i, text in enumerate(parsed):
        if i % 300 == 150:  # offset from the training stride (0) -> no overlap
            rows.append(text[:4000])
            if len(rows) >= args.limit:
                break

    out_path = Path(args.out)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["text", "label"])  # label left blank for hand-labeling
        writer.writerows((text, "") for text in rows)
    print(f"wrote {len(rows)} unlabeled rows to {out_path} — fill the `label` column with low/medium/high")


if __name__ == "__main__":
    main()
