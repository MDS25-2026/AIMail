"""TF-IDF + logistic regression baseline classifier.

This is the number the fine-tuned transformer must beat (see priority-classifier.md). Grades on
macro-F1 and per-class recall, not accuracy, because email classes are imbalanced.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.pipeline import Pipeline


def build_baseline() -> Pipeline:
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(stop_words="english", ngram_range=(1, 2))),
            ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
        ]
    )


def evaluate(model: Pipeline, texts: list[str], labels: list[str]) -> dict:
    predictions = model.predict(texts)
    return {
        "macro_f1": round(float(f1_score(labels, predictions, average="macro")), 4),
        "report": classification_report(labels, predictions, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(labels, predictions).tolist(),
        "labels": sorted(set(labels)),
    }
