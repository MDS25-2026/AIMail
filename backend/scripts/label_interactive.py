"""Interactive terminal labeler for the holdout set — step through emails, press one key each.

Shows each unlabeled email, you press h/m/l for the priority, and it saves + advances automatically.
Resumes where you left off (skips rows already labeled) and saves after every choice, so you can
quit anytime with `q` and pick up later. Deliberately shows NO suggested label — keeping your
judgment independent is the whole point of a human test set.

Usage (from backend/):
    python scripts/label_interactive.py holdout_to_label.csv
"""

import argparse
import csv
import sys
from pathlib import Path

csv.field_size_limit(10**9)

_KEYS = {"h": "high", "m": "medium", "l": "low"}


def _getch() -> str:
    """Read a single keypress without Enter (falls back to line input if not a real terminal)."""
    if not sys.stdin.isatty():
        return (sys.stdin.readline().strip()[:1] or "").lower()
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1).lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _save(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", help="holdout CSV with text + (blank) label columns")
    args = parser.parse_args()

    path = Path(args.csv)
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    total = len(rows)

    for i, row in enumerate(rows):
        if row["label"].strip():
            continue  # resume: skip already-labeled

        done = sum(1 for r in rows if r["label"].strip())
        print("\033[2J\033[H", end="")  # clear screen
        print(f"=== email {i + 1}/{total}  (labeled {done}/{total}) " + "=" * 30)
        print(row["text"][:2500])
        print("\n" + "-" * 70)
        print("HIGH: needs action / high-stakes / authority directive")
        print("MEDIUM: work-relevant, no action needed")
        print("LOW: automated, bulk, or social chit-chat")
        print("\n[h]igh  [m]edium  [l]ow   |   [s]kip   [q]uit & save")

        while True:
            key = _getch()
            if key == "q":
                _save(path, rows)
                print(f"\nsaved — {done}/{total} labeled. Run again to continue.")
                return
            if key == "s":
                break
            if key in _KEYS:
                row["label"] = _KEYS[key]
                _save(path, rows)  # save after every choice
                break

    labeled = sum(1 for r in rows if r["label"].strip())
    print(f"\ndone — {labeled}/{total} labeled and saved to {path}")


if __name__ == "__main__":
    main()
