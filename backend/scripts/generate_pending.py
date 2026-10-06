"""Pre-generate Lane C drafts for messages that don't have one yet, so opening them is instant.

Warms the cache the dashboard reads. The backend also does this automatically via a background
poller; run this for a one-off warm-up. Needs a live DB + the email agent on :8001.

Usage (from backend/):
    python scripts/generate_pending.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.dashboard import generate_pending


async def main() -> None:
    generated = await generate_pending()
    print(f"generated {generated} draft(s)")


if __name__ == "__main__":
    asyncio.run(main())
