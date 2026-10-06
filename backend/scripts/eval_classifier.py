"""Evaluate a trained importance classifier against a HUMAN-labeled holdout set.

This is the honest number for the report: the model is graded against your hand labels, not the
Gemini-generated ones it trained on. Works for either model (config PRIORITY_MODEL=baseline|distilbert).

Usage (from backend/, after you fill in holdout labels):
    python scripts/eval_classifier.py holdout_to_label.csv
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sklearn.metrics import classification_report, confusion_matrix, f1_score

from app.core.config import get_settings
from app.ml.dataset import load_dataset

if get_settings().priority_model == "distilbert":
    from app.ml.predict_transformer import predict_importance
else:
    from app.ml.predict import predict_importance

_ID_TO_LABEL = {0: "low", 1: "medium", 2: "high"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("holdout", help="CSV with text + hand-filled label columns")
    args = parser.parse_args()

    texts, gold = load_dataset(Path(args.holdout))
    if not texts:
        raise SystemExit("no labeled rows found — fill the `label` column (low/medium/high) first")

    predicted = [_ID_TO_LABEL[int(predict_importance(t)[0])] for t in texts]

    print(f"evaluated {len(texts)} hand-labeled emails using the '{get_settings().priority_model}' model\n")
    print(f"macro-F1 = {f1_score(gold, predicted, average='macro'):.4f}\n")
    print(classification_report(gold, predicted, zero_division=0))
    print("confusion matrix (rows=true, cols=pred; order low/medium/high):")
    labels = ["low", "medium", "high"]
    for label, row in zip(labels, confusion_matrix(gold, predicted, labels=labels)):
        print(f"  {label:7} {row}")


if __name__ == "__main__":
    main()
