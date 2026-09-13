"""Build a blind labelling set for evaluating `extract_actions()` recall.

Writes two files: a markdown sheet of the emails to read, and a CSV holding only row
numbers for you to type your own action-item lists into. The CSV deliberately carries
no email text and no model output — this script never opens the results file, so
annotating before seeing what the model found is structural rather than a promise.

Fill `gold_actions` with what the email asks the recipient to do, separating multiple
items with " | " (the separator the harness uses), then score with eval_actions.py.

Usage (from backend/):
    python scripts/sample_actions.py holdout_to_label.csv --limit 20
"""

import argparse
import csv
from pathlib import Path


# Deliberately duplicated from eval_critic.read_rows rather than imported: that module
# pulls in app.rag and the settings loader, and this one must not reach results at all.
def read_rows(source: Path, limit: int, offset: int) -> list[tuple[int, str]]:
    """(original_index, text) pairs — the index is the join key to critic_eval.csv."""
    with source.open(newline="", encoding="utf-8") as handle:
        all_rows = list(csv.DictReader(handle))
    selected = [
        (index, row["text"])
        for index, row in enumerate(all_rows)
        if index >= offset and row.get("text", "").strip()
    ]
    return selected[:limit]


def write_reading_file(rows: list[tuple[int, str]], out_path: Path) -> None:
    """Markdown you read while labelling."""
    blocks = [f"# Action-item labelling — {len(rows)} emails\n"]
    blocks += [f"## row {index}\n\n{text.strip()}\n\n---\n" for index, text in rows]
    out_path.write_text("\n".join(blocks), encoding="utf-8")


def write_label_file(rows: list[tuple[int, str]], out_path: Path) -> None:
    """CSV you type into. Contains no email text and no model output."""
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row", "gold_actions"])
        writer.writerows((index, "") for index, _ in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="CSV with a `text` column (e.g. holdout_to_label.csv)")
    parser.add_argument("--limit", type=int, default=20, help="emails to label")
    parser.add_argument("--offset", type=int, default=0, help="skip the first N rows of the source")
    parser.add_argument("--out-md", default="actions_to_read.md", help="the sheet you read")
    parser.add_argument("--out-csv", default="actions_to_label.csv", help="the sheet you fill in")
    args = parser.parse_args()

    rows = read_rows(Path(args.source), args.limit, args.offset)
    if not rows:
        print(f"no rows selected from {args.source} at offset {args.offset}")
        return

    write_reading_file(rows, Path(args.out_md))
    write_label_file(rows, Path(args.out_csv))
    print(f"wrote {len(rows)} emails to {args.out_md} and blank rows to {args.out_csv}")
    print('read the markdown, fill `gold_actions` with " | "-separated items, leave blank if none')


if __name__ == "__main__":
    main()
