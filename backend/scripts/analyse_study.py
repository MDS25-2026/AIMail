"""Analyse priority-calibration study responses.

Reports the three Part-1 numbers the spec requires, from the same nine items: per-participant
macro-F1 against the holdout gold, inter-participant agreement, and the model's macro-F1. Then the
Part-2 contingency table for the critic's threshold.

Fleiss' kappa is implemented here rather than pulled from statsmodels: it is fifteen lines, and a
new dependency needs sign-off. Fleiss over Krippendorff's alpha for consistency with the Cohen's
kappa already used in label_agreement.py — the ordinal caveat is printed with the number, since
low/medium/high is ordered and Fleiss treats the categories as unordered.

Expected responses CSV (one row per participant):

    participant,role,item_1,...,item_9,send_1,...,send_N,comment_1,...,comment_N

  item_*  : high | medium | low       (blank = skipped)
  send_*  : yes | edit | no           (blank = skipped)

Usage (from backend/):
    python scripts/analyse_study.py responses.csv --key study_answer_key.md
    python scripts/analyse_study.py --template          # write a blank responses CSV
"""

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

from sklearn.metrics import f1_score

_LABELS = ("low", "medium", "high")
_SEND = ("yes", "edit", "no")

# Below this, 9 items times N people is too few judgements to report a mean F1 honestly.
_MIN_PARTICIPANTS_FOR_F1 = 4


def fleiss_kappa(ratings: list[list[str]]) -> float | None:
    """Agreement across raters on the same items. `ratings[i]` are the labels given to item i.

    Returns None when every rater chose the same category for every item: agreement is total, but
    kappa is undefined there (chance agreement is 1), and printing 0.0 would invert the meaning.
    """
    items = [r for r in ratings if len(r) > 1]
    if not items:
        return None
    n_raters = len(items[0])
    if any(len(r) != n_raters for r in items):
        raise ValueError("fleiss_kappa needs the same number of raters on every item")

    counts = [[row.count(label) for label in _LABELS] for row in items]
    p_item = [
        (sum(c * c for c in row) - n_raters) / (n_raters * (n_raters - 1))
        for row in counts
    ]
    p_bar = sum(p_item) / len(p_item)
    totals = [sum(row[j] for row in counts) for j in range(len(_LABELS))]
    grand = sum(totals)
    p_expected = sum((t / grand) ** 2 for t in totals)
    if p_expected >= 1.0:
        return None
    return (p_bar - p_expected) / (1 - p_expected)


def read_key(path: Path) -> tuple[list[str], list[int]]:
    """(gold labels, holdout row indices) in item order, parsed from the generated key table."""
    gold, rows = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(low|medium|high)\s*\|", line.strip())
        if match:
            rows.append(int(match.group(2)))
            gold.append(match.group(3))
    if not gold:
        raise SystemExit(f"no gold labels parsed from {path}")
    return gold, rows


def read_responses(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def part1_labels(response: dict[str, str], n_items: int) -> list[str | None]:
    out = []
    for i in range(1, n_items + 1):
        value = (response.get(f"item_{i}") or "").strip().lower()
        out.append(value if value in _LABELS else None)
    return out


def report_part1(responses: list[dict[str, str]], gold: list[str], rows: list[int]) -> None:
    n_items = len(gold)
    per_person = {r.get("participant") or f"P{i}": part1_labels(r, n_items)
                  for i, r in enumerate(responses, 1)}
    complete = {k: v for k, v in per_person.items() if all(label is not None for label in v)}

    print(f"\n{'=' * 62}\nPART 1 — {len(responses)} participant(s), {n_items} items")
    print(f"{'=' * 62}")
    print(f"  complete responses: {len(complete)} of {len(per_person)}")

    print("\n  per-participant agreement with the gold labels:")
    for name, labels in per_person.items():
        pairs = [(g, a) for g, a in zip(gold, labels) if a is not None]
        if not pairs:
            print(f"    {name}: no usable answers")
            continue
        matches = sum(1 for g, a in pairs if g == a)
        role = (responses[list(per_person).index(name)].get("role") or "").strip() or "unstated"
        print(f"    {name} ({role}): {matches}/{len(pairs)} match", end="")
        if len(responses) >= _MIN_PARTICIPANTS_FOR_F1:
            answered_gold = [g for g, a in zip(gold, labels) if a is not None]
            answered = [a for a in labels if a is not None]
            macro = f1_score(answered_gold, answered, average="macro",
                             labels=list(_LABELS), zero_division=0)
            print(f"  macro-F1 {macro:.2f}")
        else:
            print()

    if len(responses) < _MIN_PARTICIPANTS_FOR_F1:
        print(f"\n  macro-F1 withheld: {len(responses)} participants is below "
              f"{_MIN_PARTICIPANTS_FOR_F1}. Per the spec, agreement is reported descriptively")
        print("  rather than as a statistic built on too few judgements.")

    if len(complete) > 1:
        matrix = [[labels[i] for labels in complete.values()] for i in range(n_items)]
        kappa = fleiss_kappa(matrix)
        print(f"\n  inter-participant agreement (Fleiss' kappa, n={len(complete)}): ", end="")
        print("undefined — every rater agreed on every item" if kappa is None else f"{kappa:.3f}")
        print("  caveat: Fleiss treats low/medium/high as unordered, so a low-vs-high disagreement")
        print("  counts the same as low-vs-medium. Stated for consistency with label_agreement.py.")

        print("\n  per-item spread:")
        for i, (gold_label, row) in enumerate(zip(gold, rows)):
            spread = Counter(matrix[i])
            shown = ", ".join(f"{k} {v}" for k, v in sorted(spread.items()))
            flag = "  <- unanimous" if len(spread) == 1 else ""
            print(f"    item {i + 1} (holdout row {row}, gold {gold_label}): {shown}{flag}")
    else:
        print("\n  inter-participant agreement needs 2+ complete responses")


def report_part2(responses: list[dict[str, str]]) -> None:
    send_columns = sorted(
        (c for c in responses[0] if c.startswith("send_")),
        key=lambda c: int(c.split("_")[1]),
    )
    if not send_columns:
        print("\nPART 2 — no send_* columns found, skipping")
        return

    print(f"\n{'=' * 62}\nPART 2 — {len(send_columns)} draft(s) rated")
    print(f"{'=' * 62}")
    tally: Counter[str] = Counter()
    for response in responses:
        for column in send_columns:
            value = (response.get(column) or "").strip().lower()
            if value in _SEND:
                tally[value] += 1
    total = sum(tally.values())
    if not total:
        print("  no usable Part-2 answers")
        return
    for verdict in _SEND:
        print(f"  {verdict:<6}: {tally[verdict]:>4}  ({tally[verdict] / total:.0%})")
    print("\n  The 0.8 threshold contingency table needs the per-draft critic confidence from")
    print("  study_answer_key.md joined on draft position. If every stored draft scored at or")
    print("  above 0.8, the threshold is untestable and this becomes 'does confidence")
    print("  discriminate at all' — report that, with the reason, per the spec's edge case.")


def write_template(n_items: int, n_drafts: int, path: Path) -> None:
    header = (["participant", "role"]
              + [f"item_{i}" for i in range(1, n_items + 1)]
              + [f"send_{i}" for i in range(1, n_drafts + 1)]
              + [f"comment_{i}" for i in range(1, n_drafts + 1)])
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv.writer(handle).writerow(header)
    print(f"  wrote {path} — one row per participant")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("responses", nargs="?", help="responses CSV")
    parser.add_argument("--key", default="study_answer_key.md")
    parser.add_argument("--template", action="store_true", help="write a blank responses CSV")
    parser.add_argument("--drafts", type=int, default=18, help="number of Part-2 drafts")
    parser.add_argument("--template-out", default="study_responses.csv")
    args = parser.parse_args()

    gold, rows = read_key(Path(args.key))

    if args.template:
        write_template(len(gold), args.drafts, Path(args.template_out))
        return

    if not args.responses:
        parser.error("responses CSV required (or pass --template)")

    responses = read_responses(Path(args.responses))
    if not responses:
        raise SystemExit("no responses in that file")

    report_part1(responses, gold, rows)
    report_part2(responses)
    print(f"\n{'=' * 62}")
    print(f"Report every figure above with its N: {len(responses)} participants, {len(gold)} items.")


if __name__ == "__main__":
    sys.exit(main())
