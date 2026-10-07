import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.db.models import Message
from app.db.session import get_sessionmaker


async def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    async with get_sessionmaker()() as session:
        # Get the latest message
        stmt = (
            select(Message)
            .order_by(
                Message.received_at.desc().nulls_last(), Message.created_at.desc()
            )
            .limit(1)
        )
        msg = await session.scalar(stmt)

        if not msg:
            print("No messages found in database to test with.")
            return

        print("\nTarget Message:")
        print(f"  ID:          {msg.id}")
        print(f"  Subject:     {msg.subject}")
        print(f"  Sender:      {msg.from_addr}")
        print(f"  Auth Status: {msg.auth_status or 'pass'}")
        print(f"  Has Draft:   {'Yes' if msg.draft_reply else 'No'}\n")

        if action == "spoof":
            # Set to spoof_detected and clear draft to test quarantine
            await session.execute(
                update(Message)
                .where(Message.id == msg.id)
                .values(
                    auth_status="spoof_detected", draft_reply=None, generated_at=None
                )
            )
            await session.commit()
            print("Successfully set auth_status = 'spoof_detected' and cleared draft!")
            print("Now check:")
            print(
                "1. In terminal: run 'python scripts/generate_pending.py' -> it will skip this email."
            )
            print(
                "2. In Dashboard: open this email -> see the '[!] Spoof detected' badge and Security Warning banner."
            )

        elif action == "reset":
            # Reset all spoofed messages back to pass
            result = await session.execute(
                update(Message)
                .where(Message.auth_status == "spoof_detected")
                .values(auth_status="pass")
            )
            await session.commit()
            print(
                f"Successfully reset {result.rowcount} email(s) back to auth_status = 'pass'!"
            )

        else:
            print("Usage:")
            print(
                "  python scripts/simulate_spoof.py spoof   # Simulates an SPF/DKIM spoof attack on newest email"
            )
            print(
                "  python scripts/simulate_spoof.py reset   # Resets newest email back to normal 'pass'"
            )


if __name__ == "__main__":
    asyncio.run(main())
