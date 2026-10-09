"""Load the trained 6-category B2B email taxonomy classifier and predict email category (#141).

Categories:
  - client: Client / Customer (deals, onboarding, customer support, sales)
  - vendor: Vendor / Partner (procurement, SaaS renewals, invoices, partner integrations)
  - internal: Internal / Team (sprint standups, PR reviews, 1-on-1s, engineering syncs)
  - security: Security / Compliance (SOC 2, audits, access reviews, vulnerability alerts, NDAs)
  - admin: Admin / Logistics (all-hands, room bookings, office ops, travel itineraries)
  - personal: Personal / Social (coffee catchups, lunch chats, celebrations, informal banter)

Executes in <15ms on CPU with zero network or external LLM API calls.
"""

try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):  # type: ignore[no-redef]
        pass
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.ml.clean import clean_email_text

_MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "category-classifier.joblib"


class EmailCategory(StrEnum):
    CLIENT = "client"
    VENDOR = "vendor"
    INTERNAL = "internal"
    SECURITY = "security"
    ADMIN = "admin"
    PERSONAL = "personal"


CATEGORY_DISPLAY_NAMES: dict[EmailCategory, str] = {
    EmailCategory.CLIENT: "Client / Customer",
    EmailCategory.VENDOR: "Vendor / Partner",
    EmailCategory.INTERNAL: "Internal / Team",
    EmailCategory.SECURITY: "Security / Compliance",
    EmailCategory.ADMIN: "Admin / Logistics",
    EmailCategory.PERSONAL: "Personal / Social",
}


class CategoryModelNotTrainedError(RuntimeError):
    """The category classifier artifact is missing. Run `python scripts/train_category_classifier.py` first."""


@lru_cache(maxsize=1)
def _load_model() -> Pipeline:
    if not _MODEL_PATH.exists():
        raise CategoryModelNotTrainedError(
            f"No category model artifact at {_MODEL_PATH}. Train it via `python scripts/train_category_classifier.py`"
        )
    return joblib.load(_MODEL_PATH)


def predict_category(text: str) -> tuple[EmailCategory, float]:
    """Predict the 6-category B2B taxonomy and calibrated confidence for email text.

    Args:
        text: Raw or masked email text (subject + body).

    Returns:
        tuple[EmailCategory, float]: The predicted EmailCategory and calibrated confidence (0.0 to 1.0).
    """
    cleaned = clean_email_text(text or "").strip()
    if not cleaned or len(cleaned) < 10:
        # Graceful fallback for empty, stub, or whitespace-only bodies
        return EmailCategory.INTERNAL, 0.0

    try:
        model = _load_model()
    except CategoryModelNotTrainedError:
        # Fallback when model is not yet compiled
        return EmailCategory.INTERNAL, 0.0

    raw_label = str(model.predict([cleaned])[0]).strip().lower()

    try:
        category = EmailCategory(raw_label)
    except ValueError:
        category = EmailCategory.INTERNAL

    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba([cleaned])[0]
        confidence = float(probabilities.max())
    else:
        confidence = 0.85

    return category, round(confidence, 4)
