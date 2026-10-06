"""Train + evaluate the TF-IDF baseline classifier on a labelled dataset.

Usage (from backend/, needs scikit-learn):

    python scripts/train_baseline.py <dataset.csv> [--text-col text] [--label-col label]

Writes metrics to results/baseline-metrics.json (the number the transformer must beat).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.baseline import build_baseline, evaluate
from app.ml.clean import clean_email_text
from app.ml.dataset import load_dataset, stratified_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset")
    parser.add_argument("--text-col", default="text")
    parser.add_argument("--label-col", default="label")
    args = parser.parse_args()

    texts, labels = load_dataset(Path(args.dataset), args.text_col, args.label_col)
    texts = [clean_email_text(t) for t in texts]  # match the cleaning done at inference
    print(f"loaded {len(texts)} rows; classes: {sorted(set(labels))}")

    x_train, x_test, y_train, y_test = stratified_split(texts, labels)
    model = build_baseline()
    model.fit(x_train, y_train)
    metrics = evaluate(model, x_test, y_test)

    print(f"macro-F1 = {metrics['macro_f1']}")
    for label in metrics["labels"]:
        row = metrics["report"][label]
        print(f"  {label:<12} p={row['precision']:.2f} r={row['recall']:.2f} f1={row['f1-score']:.2f}")

    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), **metrics}
    (out_dir / "baseline-metrics.json").write_text(json.dumps(payload, indent=2))
    print("wrote results/baseline-metrics.json")

    # Refit on the full dataset for the deployable artifact; the metrics above stay holdout-only.
    model.fit(texts, labels)
    model_dir = Path("models")
    model_dir.mkdir(exist_ok=True)
    joblib.dump(model, model_dir / "priority-baseline.joblib")
    print("wrote models/priority-baseline.joblib")


if __name__ == "__main__":
    main()
