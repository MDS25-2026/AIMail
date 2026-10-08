"""The migration runner: every SQL file in migrations/ applied once, in order, and recorded.

A database knows which files it has run (schema_migrations), so `make migrate` brings any environment up to
date, and an applied file that was edited afterwards is refused instead of silently diverging.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.db.session import get_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
# Two deploys starting at once must not both apply the same file.
_LOCK_KEY = "aimail_schema_migrations"

_LEDGER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    checksum   TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


class MigrationDriftError(RuntimeError):
    """An applied migration's file changed afterwards: environments would no longer match."""


@dataclass(frozen=True)
class Migration:
    version: str  # the file name without .sql, e.g. "0024_sender_auth_and_audit_chain"
    path: Path

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    return [Migration(path.stem, path) for path in sorted(directory.glob("*.sql"))]


async def _applied(conn: AsyncConnection) -> dict[str, str]:
    await conn.execute(text(_LEDGER))
    # Every public table is reachable through PostgREST; RLS with no policy keeps this one server-only.
    await conn.execute(text("ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY"))
    rows = (await conn.execute(text("SELECT version, checksum FROM schema_migrations"))).all()
    return {row.version: row.checksum for row in rows}


def _check_drift(known: list[Migration], applied: dict[str, str]) -> None:
    changed = [m.version for m in known if m.version in applied and applied[m.version] != m.checksum]
    if changed:
        raise MigrationDriftError(f"applied migrations were edited afterwards: {', '.join(changed)}")


async def _run_file(conn: AsyncConnection, migration: Migration) -> None:
    # The driver's simple-query mode runs a whole file (functions, $$ bodies) without splitting it by hand.
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(migration.path.read_text())
    await conn.execute(text("INSERT INTO schema_migrations (version, checksum) VALUES (:v, :c)"),
                       {"v": migration.version, "c": migration.checksum})


async def pending(directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Versions not yet applied; raises MigrationDriftError if an applied file changed."""
    known = migrations(directory)
    async with get_engine().begin() as conn:
        applied = await _applied(conn)
    _check_drift(known, applied)
    return [m.version for m in known if m.version not in applied]


async def apply_pending(directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every pending file in order, each in its own transaction. Returns what was applied."""
    done: list[str] = []
    async with get_engine().connect() as lock_conn:
        await lock_conn.execute(text("SELECT pg_advisory_lock(hashtext(:k))"), {"k": _LOCK_KEY})
        try:
            by_version = {m.version: m for m in migrations(directory)}
            for version in await pending(directory):
                async with get_engine().begin() as conn:
                    await _run_file(conn, by_version[version])
                done.append(version)
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(hashtext(:k))"), {"k": _LOCK_KEY})
    return done


async def baseline(up_to: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Record files up to `up_to` as applied without running them: for a database migrated by hand before."""
    known = [m for m in migrations(directory) if m.version <= up_to]
    async with get_engine().begin() as conn:
        applied = await _applied(conn)
        missing = [m for m in known if m.version not in applied]
        for migration in missing:
            await conn.execute(text("INSERT INTO schema_migrations (version, checksum) VALUES (:v, :c)"),
                               {"v": migration.version, "c": migration.checksum})
    return [m.version for m in missing]
