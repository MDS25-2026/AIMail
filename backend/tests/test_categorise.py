"""The category is classified once by the worker and stored; the inbox only reads it."""

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np

from app.dashboard import _to_email
from app.db.models import Message
from app.ml import categorise, category


def _message(**fields: object) -> Message:
    return Message(id=uuid4(), created_at=datetime(2026, 10, 9, tzinfo=timezone.utc), **fields)


def test_the_inbox_shows_the_stored_category_without_running_the_model(monkeypatch):
    def must_not_run(*_args, **_kwargs):
        raise AssertionError("the model ran while the inbox loaded")

    monkeypatch.setattr(category, "predict_category", must_not_run)
    email = _to_email(_message(category="vendor", category_confidence=0.81, body_masked="Invoice attached."))
    assert (email.category, email.categoryConfidence) == ("vendor", 0.81)


def test_an_email_not_yet_classified_keeps_the_existing_default():
    email = _to_email(_message(body_masked="Hi"))
    assert email.category == "internal" and email.categoryConfidence is None


def test_one_model_pass_gives_both_the_label_and_its_confidence(monkeypatch):
    class Model:
        classes_ = np.array(["admin", "client", "internal", "personal", "security", "vendor"])
        passes = 0

        def predict_proba(self, texts):
            Model.passes += 1
            return np.array([[0.05, 0.1, 0.05, 0.05, 0.05, 0.7]])

        def predict(self, texts):
            raise AssertionError("predict() would be a second pass")

    monkeypatch.setattr(category, "_load_model", lambda: Model())
    label, confidence = category.predict_category("Subject: Renewal\n\nYour licence renewal invoice is attached.")
    assert (label, confidence, Model.passes) == (category.EmailCategory.VENDOR, 0.7, 1)


def test_the_model_sees_the_subject_and_body_in_its_training_shape():
    assert category.category_text("Renewal", "Invoice attached.") == "Subject: Renewal\n\nInvoice attached."


def test_nothing_is_stored_while_the_model_is_missing(monkeypatch):
    monkeypatch.setattr(categorise, "is_model_available", lambda: False)
    assert asyncio.run(categorise.classify_pending(limit=10)) == 0  # never reaches the database


def test_the_container_image_includes_the_category_model():
    backend = Path(__file__).resolve().parent.parent
    assert "!models/category-classifier.joblib" in (backend / ".dockerignore").read_text().splitlines()
    assert "COPY models/category-classifier.joblib ./models/" in (backend / "Dockerfile").read_text()


class _Rows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class _Session:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    def begin(self):
        return self

    async def execute(self, _statement):
        return _Rows(self.rows)


def test_classifying_never_stalls_the_api_sharing_its_process(monkeypatch):
    """On a small host the API and the worker share one event loop (app/combined.py)."""
    row = type("Row", (), {"id": uuid4(), "subject": "Invoice", "body_masked": "Please pay the invoice."})()

    def slow_prediction(_text):
        time.sleep(0.4)  # the model doing CPU work
        return category.EmailCategory.VENDOR, 0.9

    monkeypatch.setattr(categorise, "is_model_available", lambda: True)
    monkeypatch.setattr(categorise, "predict_category", slow_prediction)
    monkeypatch.setattr(categorise, "get_sessionmaker", lambda: lambda: _Session([row]))

    async def scenario():
        ticks = 0

        async def api_requests():
            nonlocal ticks
            for _ in range(10):
                await asyncio.sleep(0.02)
                ticks += 1

        await asyncio.gather(categorise.classify_pending(limit=5), api_requests())
        return ticks

    started = time.monotonic()
    # Side by side it takes about the longer of the two (0.4 s); a stalled loop takes their sum (0.6 s).
    assert asyncio.run(scenario()) == 10 and time.monotonic() - started < 0.55
