"""Reconcile the blind 3-way category audit and compute inter-annotator agreement (#141).

Usage:
    python scripts/reconcile_category_audit.py [--gold-out data/category/holdout_gold.csv]

Functionality:
1. Validates that Han, JJ, and Hanif completed their audit rows in holdout_audit.csv.
2. Computes pairwise Cohen's Kappa (and average agreement) across the 12 shared calibration rows.
3. Builds the reconciled human ground-truth dataset and saves it to holdout_gold.csv.
4. Triggers eval_category_classifier.py to produce audited metrics for Poster Section 05.
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"client", "vendor", "internal", "security", "admin", "personal"}


def compute_inter_rater_agreement(df_shared: pd.DataFrame) -> dict[str, float]:
    """Compute pairwise Cohen's Kappa on the 12 shared calibration rows."""
    reviewers = [("Han", "han_label"), ("JJ", "jj_label"), ("Hanif", "hanif_label")]
    kappas: dict[str, float] = {}

    for i in range(len(reviewers)):
        for j in range(i + 1, len(reviewers)):
            name_a, col_a = reviewers[i]
            name_b, col_b = reviewers[j]

            labels_a = [str(x).strip().lower() for x in df_shared[col_a]]
            labels_b = [str(x).strip().lower() for x in df_shared[col_b]]

            # Filter valid
            if any(la not in VALID_CATEGORIES for la in labels_a) or any(lb not in VALID_CATEGORIES for lb in labels_b):
                logger.warning("Shared rows contain unlabelled or invalid categories. Skipping kappa for %s vs %s", name_a, name_b)
                continue

            score = cohen_kappa_score(labels_a, labels_b)
            pair_key = f"{name_a}_vs_{name_b}"
            kappas[pair_key] = round(float(score), 4)

    if kappas:
        kappas["mean_kappa"] = round(float(sum(kappas.values()) / len(kappas)), 4)

    return kappas


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile 3-way blind category audit.")
    parser.add_argument("--audit-csv", default="data/category/holdout_audit.csv", help="Audit CSV path")
    parser.add_argument("--gold-out", default="data/category/holdout_gold.csv", help="Output gold CSV path")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    audit_path = Path(args.audit_csv) if Path(args.audit_csv).is_absolute() else root / args.audit_csv
    gold_path = Path(args.gold_out) if Path(args.gold_out).is_absolute() else root / args.gold_out

    if not audit_path.exists():
        logger.error("Audit file not found at %s", audit_path)
        sys.exit(1)

    df = pd.read_csv(audit_path)
    logger.info("Loaded audit sheet with %d rows from %s", len(df), audit_path)

    # 1. Evaluate shared rows (rows 1-12)
    df_shared = df[df["assigned_reviewer"] == "ALL"].copy()
    logger.info("Inspecting %d shared calibration rows for inter-annotator agreement...", len(df_shared))

    kappas = compute_inter_rater_agreement(df_shared)
    if kappas:
        print("\n" + "=" * 60)
        print("INTER-ANNOTATOR AGREEMENT (COHEN'S KAPPA ON 12 SHARED ROWS)")
        print("=" * 60)
        for pair, score in kappas.items():
            print(f"Pairwise {pair:<20}: {score:.4f}")
        print("=" * 60 + "\n")
    else:
        logger.warning("Shared calibration rows are not yet completely filled in.")

    # 2. Extract reconciled labels
    reconciled_labels: list[str] = []
    missing_ids: list[int] = []

    for _, row in df.iterrows():
        row_id = int(row["id"])
        reviewer = str(row["assigned_reviewer"]).strip()

        # Check explicit consensus first
        consensus = str(row.get("consensus_category", "")).strip().lower()
        if consensus in VALID_CATEGORIES:
            reconciled_labels.append(consensus)
            continue

        label = ""
        if reviewer == "ALL":
            # Majority vote across Han, JJ, Hanif
            votes = [
                str(row.get("han_label", "")).strip().lower(),
                str(row.get("jj_label", "")).strip().lower(),
                str(row.get("hanif_label", "")).strip().lower(),
            ]
            valid_votes = [v for v in votes if v in VALID_CATEGORIES]
            if valid_votes:
                # Plurality / mode
                label = max(set(valid_votes), key=valid_votes.count)
        elif reviewer == "Han":
            label = str(row.get("han_label", "")).strip().lower()
        elif reviewer == "JJ":
            label = str(row.get("jj_label", "")).strip().lower()
        elif reviewer == "Hanif":
            label = str(row.get("hanif_label", "")).strip().lower()

        if label in VALID_CATEGORIES:
            reconciled_labels.append(label)
        else:
            missing_ids.append(row_id)
            reconciled_labels.append("")

    if missing_ids:
        logger.warning("Audit sheet is incomplete! Missing or invalid labels on %d rows: %s", len(missing_ids), missing_ids[:10])
        print(f"Please ensure all reviewers fill their rows. Incomplete row count: {len(missing_ids)} / {len(df)}")
        return

    # 3. Write reconciled gold file
    df_reconciled = pd.DataFrame({
        "text": df["text"],
        "category": reconciled_labels,
    })
    df_reconciled.to_csv(gold_path, index=False)
    logger.info("Successfully exported %d reconciled gold samples to %s", len(df_reconciled), gold_path)

    # 4. Trigger evaluation re-run
    eval_script = root / "scripts" / "eval_category_classifier.py"
    if eval_script.exists():
        logger.info("Re-running empirical evaluation on newly reconciled gold dataset...")
        subprocess.run([sys.executable, str(eval_script), str(gold_path)], check=True)


if __name__ == "__main__":
    main()
