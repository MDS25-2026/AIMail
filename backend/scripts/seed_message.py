"""Insert a sample row into `messages` so /emails can be tested without the Gmail listener.

Usage (from backend/, needs a live DB with 0002_messages.sql applied):
    python scripts/seed_message.py

Simulates what Lane A's listener writes. The sample is a supplier "gift" email, which the Lane C
draft will ground against the Code of Conduct gift policy (once that doc is ingested).
"""

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Message
from app.db.session import get_sessionmaker


async def main() -> None:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session, session.begin():
        session.add(
            Message(
                gmail_message_id="seed-001",
                from_addr="supplier@vendor.com",
                subject="Gift for the team",
                body_masked=(
                    "Hi, we would like to send your team a gift to thank you for the partnership. "
                    "Please confirm a delivery address by Friday."
                ),
                snippet_masked="Hi, we would like to send your team a gift...",
                emails_masked=1,
                phones_masked=0,
                received_at=datetime.now(timezone.utc),
            )
        )
    print("seeded one sample message into `messages`")


if __name__ == "__main__":
    asyncio.run(main())
