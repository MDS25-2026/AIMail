"""Analyse priority-calibration study responses.

Reports the three Part-1 numbers the spec requires, from the same nine items: per-participant
macro-F1 against the holdout gold, inter-participant agreement, and the model's macro-F1. Then the
Part-2 contingency table for the critic's threshold.

Fleiss' kappa is implemented here rather than pulled from statsmodels: it is fifteen lines, and a
new dependency needs sign-off. Fleiss over Krippendorff's alpha for consistency with the Cohen's
kappa already used in label_agreement.py — the ordinal caveat is printed with the number, since
low/medium/high is ordered and Fleiss treats the categories as unordered.

Expected responses CSV (one row per participant) — `--template` writes the header for you:

  item_1..9     high | medium | low                       (blank = skipped)
  explain_4/7/8 free text, the three diagnostic items
  q1/q2         free text, the two closing questions
  g1_N..g4_N    the four gate checks on draft N
  send_N        yes | edit | no
  comment_N     free text

The four gate columns are the point of Part 2 and are reported separately, per #78: one overall
verdict cannot say which gate carries signal and which is noise.

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


# Human answers that mean "this gate should have failed". Anything else (including "not sure")
# counts as no complaint — treating uncertainty as a failure would inflate every disagreement.
_GATE_FAILS = {
    "g1": {"yes", "yes, it invents something"},
    "g2": {"yes"},
    "g3": {"too formal", "too casual", "something else is off"},
    "g4": {"it misses part of it", "it misses most of it"},
}
_GATE_NAMES = {"g1": "grounding_ok", "g2": "pii_clean", "g3": "tone_match", "g4": "completeness"}


def report_part2(responses: list[dict[str, str]], key_rows: list[dict[str, str]]) -> None:
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

    print("  overall verdicts:")
    for verdict in _SEND:
        print(f"    {verdict:<6}: {tally[verdict]:>4}  ({tally[verdict] / total:.0%})")

    # Per gate, not just overall: #78 requires each analysed separately, because one holistic
    # number cannot say which gate carries signal and which is noise.
    print("\n  per-gate: how often a human said this gate should have failed")
    for gate, name in _GATE_NAMES.items():
        complaints, answered = 0, 0
        for response in responses:
            for index in range(1, len(send_columns) + 1):
                value = (response.get(f"{gate}_{index}") or "").strip().lower()
                if not value:
                    continue
                answered += 1
                if value in _GATE_FAILS[gate]:
                    complaints += 1
        if not answered:
            print(f"    {name:<14} no answers")
            continue
        print(f"    {name:<14} {complaints}/{answered} ({complaints / answered:.0%})")

    if key_rows:
        print("\n  human complaints against what the critic flagged, per draft:")
        for index, row in enumerate(key_rows, 1):
            gates_complained = []
            for gate, name in _GATE_NAMES.items():
                hits = sum(
                    1 for r in responses
                    if (r.get(f"{gate}_{index}") or "").strip().lower() in _GATE_FAILS[gate]
                )
                if hits:
                    gates_complained.append(f"{name}x{hits}")
            critic = row.get("reason") or ("flagged" if row.get("flagged") == "True" else "clean")
            humans = ", ".join(gates_complained) or "no complaints"
            print(f"    draft {index} (conf {row.get('confidence')}, critic: {critic})")
            print(f"              humans: {humans}")
        print("\n  The rows where the critic said clean and humans complained — or the reverse —")
        print("  are the finding. Report them per gate, not as one agreement percentage.")

    print("\n  The 0.8 threshold itself is untestable on stored drafts: REFINE_THRESHOLD is 0.8,")
    print("  so the refine loop guarantees nothing below it survives. Testing it needs pre-refine")
    print("  confidence persisted. Report that reason rather than 'insufficient data'.")


def read_key_rows(path: Path) -> list[dict[str, str]]:
    """Part-2 key table: confidence, whether the critic flagged it, and on what ground."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(
            r"\|\s*(\d+)\s*\|\s*([0-9a-f-]{36})\s*\|\s*([\d.]+|null)\s*\|\s*(True|False)\s*\|\s*(.*?)\s*\|",
            line.strip(),
        )
        if match:
            rows.append({"position": match.group(1), "id": match.group(2),
                         "confidence": match.group(3), "flagged": match.group(4),
                         "reason": match.group(5) if match.group(5) != "-" else ""})
    return rows


def write_template(n_items: int, n_drafts: int, path: Path) -> None:
    header = (["participant", "role"]
              + [f"item_{i}" for i in range(1, n_items + 1)]
              + [f"explain_{i}" for i in (4, 7, 8)]
              + ["q1_not_fitting", "q2_sender_list"]
              + [f"{gate}_{i}" for i in range(1, n_drafts + 1) for gate in _GATE_NAMES]
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
    parser.add_argument("--drafts", type=int, default=6, help="number of Part-2 drafts")
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
    report_part2(responses, read_key_rows(Path(args.key)))
    print(f"\n{'=' * 62}")
    print(f"Report every figure above with its N: {len(responses)} participants, {len(gold)} items.")


if __name__ == "__main__":
    sys.exit(main())
