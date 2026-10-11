"""scripts/backup.py keeps only the newest dumps, so erased data does not live on in old ones."""

from scripts import backup


def test_only_the_newest_dumps_are_kept_and_other_files_are_left_alone(tmp_path):
    names = [f"aimail-202610{day:02d}T010000Z.dump" for day in range(1, 11)]
    for name in [*names, "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")
    removed = backup.prune(tmp_path, keep=7)
    assert [path.name for path in removed] == names[:3]
    assert [path.name for path in backup.dumps(tmp_path)] == names[3:]
    assert (tmp_path / "notes.txt").exists()


def test_the_database_address_never_appears_on_the_command_line():
    assert "PGURL" in backup.PG_DUMP and "postgresql://" not in backup.PG_DUMP
