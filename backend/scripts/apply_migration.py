"""Apply a SQL migration to the configured database.

Usage (from backend/, with DATABASE_URL set in the repo-root .env):

    python scripts/apply_migration.py [path/to/file.sql]

Defaults to the RAG tables migration. First run only — re-running fails on
existing tables (add IF NOT EXISTS or drop first if you need to re-apply).
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.migrate import apply_sql_file

_DEFAULT = Path(__file__).resolve().parent.parent / "app" / "db" / "migrations" / "0001_rag_tables.sql"


async def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT
    count = await apply_sql_file(path)
    print(f"applied {path.name}: {count} statements")


if __name__ == "__main__":
    asyncio.run(main())
