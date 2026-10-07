import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import get_engine


async def main():
    if len(sys.argv) < 2:
        print("Usage: python run_sql.py <path_to_sql>")
        return
    path = Path(sys.argv[1])
    sql = path.read_text()

    engine = get_engine()
    async with engine.begin() as conn:
        # Get raw asyncpg connection
        raw_conn = await conn.get_raw_connection()
        await raw_conn.driver_connection.execute(sql)
    print("Migration applied successfully!")


if __name__ == "__main__":
    asyncio.run(main())
