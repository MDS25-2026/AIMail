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
import logging
from functools import lru_cache
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.ml.clean import clean_email_text

logger = logging.getLogger(__name__)

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


@lru_cache(maxsize=1)
def _load_model() -> Pipeline | None:
    """Loaded once. A missing artifact is logged once here, not swallowed on every email."""
    if not _MODEL_PATH.exists():
        logger.error("category model missing at %s: every email falls back to internal; "
                     "train it with scripts/train_category_classifier.py", _MODEL_PATH)
        return None
    return joblib.load(_MODEL_PATH)


def is_model_available() -> bool:
    return _load_model() is not None


def category_text(subject: str | None, body: str | None) -> str:
    """The shape the model was trained on: a subject line, a blank line, then the body."""
    return f"Subject: {subject or ''}\n\n{body or ''}"


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

    model = _load_model()
    if model is None:
        return EmailCategory.INTERNAL, 0.0

    # One pass: the most probable class is the label, and its probability is the confidence.
    probabilities = model.predict_proba([cleaned])[0]
    best = int(probabilities.argmax())
    raw_label = str(model.classes_[best]).strip().lower()
    try:
        category = EmailCategory(raw_label)
    except ValueError:
        category = EmailCategory.INTERNAL
    return category, round(float(probabilities[best]), 4)
