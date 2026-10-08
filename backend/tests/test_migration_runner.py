"""The migration runner (app/db/migrate.py): order, and refusing edited migrations."""

import pytest

from app.db import migrate
from app.db.migrate import MigrationDriftError


def test_migrations_run_in_file_order():
    versions = [m.version for m in migrate.migrations()]
    assert versions == sorted(versions) and versions[0].startswith("0001_")


def test_every_migration_has_a_unique_number():
    numbers = [m.version.split("_", 1)[0] for m in migrate.migrations()]
    assert len(numbers) == len(set(numbers))


def test_an_applied_migration_that_was_edited_is_refused(tmp_path):
    (tmp_path / "0001_first.sql").write_text("SELECT 1;")
    known = migrate.migrations(tmp_path)
    with pytest.raises(MigrationDriftError, match="0001_first"):
        migrate._check_drift(known, {"0001_first": "a checksum from before the edit"})


def test_unchanged_applied_migrations_pass(tmp_path):
    (tmp_path / "0001_first.sql").write_text("SELECT 1;")
    known = migrate.migrations(tmp_path)
    migrate._check_drift(known, {"0001_first": known[0].checksum})
