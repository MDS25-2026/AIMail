"""Load the trained baseline and predict email importance.

Maps the model's string label to the Importance enum. Raises on a missing model or an
unrecognized label rather than defaulting — a silent default here would reproduce the
priority_label(None) placeholder bug the dashboard already has.
"""

from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.ml.types import Importance

_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "priority-baseline.joblib"

_LABEL_TO_IMPORTANCE: dict[str, Importance] = {
    "low": Importance.LOW,
    "medium": Importance.MEDIUM,
    "high": Importance.HIGH,
}


class ModelNotTrainedError(RuntimeError):
    """The baseline artifact is missing — run `make baseline DATASET=...` first."""


class UnknownLabelError(ValueError):
    """The model emitted a label outside the low/medium/high taxonomy."""


@lru_cache(maxsize=1)
def _load_model() -> Pipeline:
    if not _MODEL_PATH.exists():
        raise ModelNotTrainedError(f"no model at {_MODEL_PATH}; run `make baseline DATASET=...`")
    return joblib.load(_MODEL_PATH)


def predict_importance(text: str) -> tuple[Importance, float]:
    model = _load_model()
    label = str(model.predict([text])[0]).strip().lower()
    importance = _LABEL_TO_IMPORTANCE.get(label)
    if importance is None:
        raise UnknownLabelError(f"model produced unrecognized label {label!r}; expected low/medium/high")
    confidence = float(model.predict_proba([text]).max())
    return importance, round(confidence, 4)
