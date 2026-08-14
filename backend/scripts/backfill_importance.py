"""Predict importance for messages and store it, so the dashboard badge shows a real prediction.

Runs the trained baseline (see train_baseline.py) over messages and writes the predicted
importance + confidence back to the row. Without this, priority_label(None) shows a placeholder
MEDIUM for every email. By default it only scores unclassified messages; --all rescores every row
(use after retraining).

Usage (from backend/, needs a trained model + live DB):
    python scripts/backfill_importance.py
    python scripts/backfill_importance.py --all
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.models import Message
from app.db.session import get_sessionmaker
from app.ml.predict import predict_importance

_MODEL_VERSION = "baseline-tfidf-lr-v1"


async def main(rescore_all: bool) -> None:
    stmt = select(Message)
    if not rescore_all:
        stmt = stmt.where(Message.importance.is_(None))

    async with get_sessionmaker()() as session, session.begin():
        rows = (await session.scalars(stmt)).all()
        for message in rows:
            text = f"{message.subject or ''}\n{message.body_masked or ''}".strip()
            importance, confidence = predict_importance(text)
            message.importance = int(importance)
            message.importance_confidence = confidence
            message.importance_model_version = _MODEL_VERSION
    print(f"scored {len(rows)} message(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="rescore every message, not just unclassified")
    asyncio.run(main(parser.parse_args().all))
