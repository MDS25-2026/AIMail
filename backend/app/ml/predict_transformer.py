"""Predict email importance with the fine-tuned DistilBERT model.

Mirrors predict.py's interface (returns Importance + confidence) so backfill_importance.py can swap
it in. Imports torch/transformers lazily inside the function, so the API process never loads them
unless DistilBERT is actually used.
"""

from functools import lru_cache
from pathlib import Path

from app.ml.types import Importance

_MODEL_DIR = Path(__file__).resolve().parents[2] / "models" / "distilbert"
_ID_TO_IMPORTANCE = {0: Importance.LOW, 1: Importance.MEDIUM, 2: Importance.HIGH}


class ModelNotTrainedError(RuntimeError):
    """The DistilBERT artifact is missing — run `make distilbert` first."""


@lru_cache(maxsize=1)
def _pipeline():
    if not _MODEL_DIR.exists():
        raise ModelNotTrainedError(f"no model at {_MODEL_DIR}; run `make distilbert`")
    from transformers import pipeline  # lazy: keep torch out of the API import path

    return pipeline("text-classification", model=str(_MODEL_DIR), tokenizer=str(_MODEL_DIR), truncation=True)


def predict_importance(text: str) -> tuple[Importance, float]:
    result = _pipeline()(text)[0]  # {"label": "low"/"medium"/"high", "score": 0..1}
    label_id = {"low": 0, "medium": 1, "high": 2}[result["label"].lower()]
    return _ID_TO_IMPORTANCE[label_id], round(float(result["score"]), 4)
