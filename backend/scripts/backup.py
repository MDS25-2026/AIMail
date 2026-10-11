"""Dump the database's public schema to a file outside the repo, keeping the last BACKUP_KEEP dumps.

pg_dump must be at least the server's major version (Supabase runs 17), so it runs from a pinned
postgres:17 image rather than whatever client is installed. The URL reaches the container as an
environment variable, never on a command line. Dumps hold email content (masked) and sealed vaults:
the folder is private to the user, and erasure does not reach a dump, so old ones are deleted.

Usage (from backend/): python scripts/backup.py            make a dump, prune old ones
                       python scripts/backup.py --list     show the dumps kept
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings

PG_DUMP_IMAGE = "postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24"  # 17-alpine
DUMP_PREFIX = "aimail-"
DUMP_SUFFIX = ".dump"
PRIVATE_DIR = 0o700
PRIVATE_FILE = 0o600
PG_DUMP = 'exec pg_dump "$PGURL" --schema=public --no-owner --no-privileges --format=custom'


def backup_dir() -> Path:
    folder = Path(get_settings().backup_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    folder.chmod(PRIVATE_DIR)
    return folder


def dumps(folder: Path) -> list[Path]:
    """Oldest first: the timestamp in the name sorts as time does."""
    return sorted(folder.glob(f"{DUMP_PREFIX}*{DUMP_SUFFIX}"))


def make_dump(folder: Path) -> Path:
    """A finished dump, or SystemExit with pg_dump's own message; a partial file is never kept."""
    target = folder / f"{DUMP_PREFIX}{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}{DUMP_SUFFIX}"
    partial = target.with_suffix(".partial")
    env = os.environ | {"PGURL": get_settings().database_url}
    command = ["docker", "run", "--rm", "-e", "PGURL", PG_DUMP_IMAGE, "sh", "-c", PG_DUMP]
    with partial.open("wb") as out:
        partial.chmod(PRIVATE_FILE)
        result = subprocess.run(command, stdout=out, stderr=subprocess.PIPE, env=env, check=False)
    if result.returncode != 0:
        partial.unlink()
        raise SystemExit(f"pg_dump failed: {result.stderr.decode(errors='replace').strip()}")
    return partial.rename(target)


def prune(folder: Path, keep: int) -> list[Path]:
    old = dumps(folder)[:-keep]
    for path in old:
        path.unlink()
    return old


def main(show_only: bool) -> None:
    if not get_settings().database_url:
        raise SystemExit("DATABASE_URL is not set")
    folder = backup_dir()
    if show_only:
        for path in dumps(folder):
            print(f"{path.name}  {path.stat().st_size / 1_000_000:.1f} MB")
        return
    made = make_dump(folder)
    removed = prune(folder, get_settings().backup_keep)
    print(f"kept {made.name} ({made.stat().st_size / 1_000_000:.1f} MB) in {folder}; removed {len(removed)} older")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="show the dumps kept")
    main(parser.parse_args().list)
