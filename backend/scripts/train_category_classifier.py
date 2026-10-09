"""Train and evaluate the 6-category B2B email taxonomy classifier (#141).

Taxonomy:
  1. client: Client / Customer
  2. vendor: Vendor / Partner
  3. internal: Internal / Team
  4. security: Security / Compliance
  5. admin: Admin / Logistics
  6. personal: Personal / Social

Usage (from backend/):
  python scripts/train_category_classifier.py [data/category/train.csv]

Outputs:
  - models/category-classifier.joblib (deployable artifact, <5ms CPU latency)
  - results/category-validation-metrics.json (macro-F1, per-class metrics)
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.clean import clean_email_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CATEGORIES = ["client", "vendor", "internal", "security", "admin", "personal"]


def build_pipeline() -> Pipeline:
    """Construct TF-IDF + Logistic Regression pipeline optimized for short-to-medium emails."""
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=12_000,
                    sublinear_tf=True,
                    stop_words="english",
                    strip_accents="unicode",
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=2.0,
                    max_iter=1000,
                    class_weight="balanced",
                    solver="lbfgs",
                    random_state=42,
                ),
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train 6-category B2B email classifier.")
    parser.add_argument("dataset", nargs="?", default="data/category/train.csv", help="Path to training CSV")
    parser.add_argument("--text-col", default="text", help="Text column name")
    parser.add_argument("--label-col", default="category", help="Category label column name")
    args = parser.parse_args()

    data_path = Path(args.dataset)
    if not data_path.is_absolute():
        data_path = Path(__file__).resolve().parent.parent / data_path

    if not data_path.exists():
        logger.error("Dataset not found at %s. Run `python scripts/generate_category_dataset.py` first.", data_path)
        sys.exit(1)

    df = pd.read_csv(data_path)
    df = df.dropna(subset=[args.text_col, args.label_col])
    texts = [clean_email_text(str(t)) for t in df[args.text_col]]
    labels = [str(l).strip().lower() for l in df[args.label_col]]

    logger.info("Loaded %d rows across %d categories: %s", len(texts), len(set(labels)), sorted(set(labels)))

    # Stratified 80/20 train/validation split
    x_train, x_val, y_train, y_val = train_test_split(
        texts, labels, test_size=0.20, random_state=42, stratify=labels
    )

    logger.info("Split: %d training rows, %d validation rows", len(x_train), len(x_val))

    pipeline = build_pipeline()

    # Stratified Cross Validation (guarded for dataset size)
    min_class_count = min(pd.Series(y_train).value_counts())
    n_splits = min(5, min_class_count)
    if n_splits >= 2:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        cv_scores = cross_val_score(pipeline, x_train, y_train, cv=cv, scoring="f1_macro")
        logger.info("%d-Fold Cross-Validation Macro-F1: %.4f (std: %.4f)", n_splits, cv_scores.mean(), cv_scores.std())
    else:
        cv_scores = None

    # Fit on training partition
    pipeline.fit(x_train, y_train)

    # Evaluate on held-out validation split
    val_preds = pipeline.predict(x_val)
    macro_f1 = f1_score(y_val, val_preds, average="macro")
    report = classification_report(y_val, val_preds, output_dict=True, zero_division=0)
    conf_matrix = confusion_matrix(y_val, val_preds, labels=sorted(set(labels)))

    print("\n" + "=" * 60)
    print(f"VALIDATION MACRO-F1: {macro_f1:.4f}")
    print("=" * 60)
    for cat in sorted(set(labels)):
        if cat in report:
            row = report[cat]
            print(f"  {cat:<12} Precision: {row['precision']:.2f} | Recall: {row['recall']:.2f} | F1: {row['f1-score']:.2f}")
    print("=" * 60 + "\n")

    # Persist validation metrics
    results_dir = Path(__file__).resolve().parent.parent / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    metrics_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_samples": len(texts),
        "validation_samples": len(x_val),
        "macro_f1": round(float(macro_f1), 4),
        "cv_macro_f1_mean": round(float(cv_scores.mean()), 4) if cv_scores is not None else None,
        "cv_macro_f1_std": round(float(cv_scores.std()), 4) if cv_scores is not None else None,
        "classification_report": report,
        "confusion_matrix": conf_matrix.tolist(),
        "labels": sorted(set(labels)),
    }
    (results_dir / "category-validation-metrics.json").write_text(json.dumps(metrics_payload, indent=2))
    logger.info("Saved validation metrics to results/category-validation-metrics.json")

    # Final refit on the full dataset for the deployable model
    logger.info("Refitting pipeline on all %d samples for deployment...", len(texts))
    pipeline.fit(texts, labels)

    models_dir = Path(__file__).resolve().parent.parent / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_artifact = models_dir / "category-classifier.joblib"
    joblib.dump(pipeline, model_artifact)
    logger.info("Saved trained classifier artifact to %s", model_artifact)


if __name__ == "__main__":
    main()
