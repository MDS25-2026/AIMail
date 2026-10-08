"""Evaluate the trained 6-category B2B email taxonomy classifier against the gold holdout set (#141).

Outputs:
  - results/category_metrics.json (Macro-F1, per-class metrics, CPU inference latency)
  - results/category_confusion_matrix.png (300 DPI high-resolution publication plot for Poster Section 05)

Usage (from backend/):
  python scripts/eval_category_classifier.py [data/category/holdout_gold.csv]
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ml.category import CATEGORY_DISPLAY_NAMES, EmailCategory
from app.ml.clean import clean_email_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CATEGORY_ORDER = [
    EmailCategory.CLIENT.value,
    EmailCategory.VENDOR.value,
    EmailCategory.INTERNAL.value,
    EmailCategory.SECURITY.value,
    EmailCategory.ADMIN.value,
    EmailCategory.PERSONAL.value,
]


def plot_confusion_matrix(cm, labels, display_labels, out_path: Path) -> None:
    from sklearn.metrics import ConfusionMatrixDisplay

    fig, ax = plt.subplots(figsize=(8.0, 6.5), dpi=200)
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=display_labels)
    disp.plot(ax=ax, cmap="Blues", colorbar=True, values_format="d")

    plt.setp(ax.get_xticklabels(), rotation=25, ha="right", rotation_mode="anchor", fontsize=9)
    plt.setp(ax.get_yticklabels(), fontsize=9)

    ax.set_title(
        "B2B Email Taxonomy Classifier Confusion Matrix\n(Evaluated on Held-Out Human-Audited Gold Split)",
        fontsize=11,
        fontweight="bold",
        pad=14,
    )
    ax.set_xlabel("Predicted Category", fontsize=10, fontweight="bold", labelpad=8)
    ax.set_ylabel("Actual Ground Truth Category", fontsize=10, fontweight="bold", labelpad=8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()
    logger.info("Exported confusion matrix heatmap to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate 6-category B2B classifier on holdout gold split.")
    parser.add_argument("gold_csv", nargs="?", default="data/category/holdout_gold.csv", help="Path to gold CSV")
    parser.add_argument("--model", default="models/category-classifier.joblib", help="Model artifact path")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    gold_path = Path(args.gold_csv) if Path(args.gold_csv).is_absolute() else root / args.gold_csv
    model_path = Path(args.model) if Path(args.model).is_absolute() else root / args.model

    if not model_path.exists():
        logger.error("Model artifact not found at %s. Run `python scripts/train_category_classifier.py` first.", model_path)
        sys.exit(1)

    if not gold_path.exists():
        logger.error("Gold holdout dataset not found at %s. Run `python scripts/generate_category_dataset.py` first.", gold_path)
        sys.exit(1)

    df = pd.read_csv(gold_path).dropna(subset=["text", "category"])
    texts = [clean_email_text(str(t)) for t in df["text"]]
    gold_labels = [str(l).strip().lower() for l in df["category"]]

    model = joblib.load(model_path)
    logger.info("Loaded model artifact from %s", model_path)

    # Benchmark CPU inference latency
    logger.info("Benchmarking CPU inference latency over %d samples...", len(texts))
    start_time = time.perf_counter()
    preds = model.predict(texts)
    total_latency_ms = (time.perf_counter() - start_time) * 1000
    avg_latency_ms = total_latency_ms / len(texts)
    logger.info("Total inference time: %.2fms | Average latency: %.2fms per email (<50ms SLA gate: %s)",
                total_latency_ms, avg_latency_ms, "PASS" if avg_latency_ms < 50.0 else "FAIL")

    # Evaluate Macro-F1 and per-class metrics
    macro_f1 = f1_score(gold_labels, preds, average="macro")
    report = classification_report(gold_labels, preds, labels=CATEGORY_ORDER, output_dict=True, zero_division=0)
    cm = confusion_matrix(gold_labels, preds, labels=CATEGORY_ORDER)

    display_labels = [CATEGORY_DISPLAY_NAMES[EmailCategory(c)] for c in CATEGORY_ORDER]

    print("\n" + "=" * 70)
    print(f"EMPIRICAL EVALUATION RESULTS (GOLDOUT TEST SET)")
    print("=" * 70)
    print(f"Macro F1-Score:           {macro_f1:.4f}  (Gate: >= 0.8500 -> {'PASS' if macro_f1 >= 0.85 else 'REVIEW'})")
    print(f"Average CPU Latency:      {avg_latency_ms:.2f} ms  (Gate: < 50.0 ms -> {'PASS' if avg_latency_ms < 50.0 else 'FAIL'})")
    print(f"Test Set Evaluation Size: {len(texts)} emails")
    print("-" * 70)
    print(f"{'Category':<24} {'Precision':<10} {'Recall':<10} {'F1-Score':<10} {'Support':<8}")
    print("-" * 70)
    for cat_key, disp_name in zip(CATEGORY_ORDER, display_labels):
        row = report.get(cat_key, {"precision": 0.0, "recall": 0.0, "f1-score": 0.0, "support": 0})
        print(f"{disp_name:<24} {row['precision']:<10.2f} {row['recall']:<10.2f} {row['f1-score']:<10.2f} {int(row['support']):<8}")
    print("=" * 70 + "\n")

    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Export metrics JSON
    metrics_payload = {
        "evaluation_timestamp": datetime.now(timezone.utc).isoformat(),
        "holdout_samples": len(texts),
        "macro_f1": round(float(macro_f1), 4),
        "average_cpu_latency_ms": round(float(avg_latency_ms), 2),
        "latency_gate_passed": avg_latency_ms < 50.0,
        "f1_gate_passed": macro_f1 >= 0.85,
        "per_class_report": {cat: report.get(cat, {}) for cat in CATEGORY_ORDER},
        "confusion_matrix": cm.tolist(),
        "categories": CATEGORY_ORDER,
        "display_categories": display_labels,
    }
    metrics_file = results_dir / "category_metrics.json"
    metrics_file.write_text(json.dumps(metrics_payload, indent=2))
    logger.info("Saved evaluation metrics JSON to %s", metrics_file)

    # Export 300 DPI Confusion Matrix plot
    cm_plot_path = results_dir / "category_confusion_matrix.png"
    plot_confusion_matrix(cm, CATEGORY_ORDER, display_labels, cm_plot_path)


if __name__ == "__main__":
    main()
