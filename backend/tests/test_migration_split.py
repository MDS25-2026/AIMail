from pathlib import Path

from app.db.migrate import split_statements

_MIGRATION = Path(__file__).resolve().parents[1] / "app" / "db" / "migrations" / "0001_rag_tables.sql"


def test_split_yields_all_statements_including_leading_extension():
    statements = split_statements(_MIGRATION.read_text())
    assert len(statements) == 6  # CREATE EXTENSION + 3 tables + 2 indexes
    assert statements[0] == "CREATE EXTENSION IF NOT EXISTS vector"
    assert any(s.startswith("CREATE TABLE document") for s in statements)
    assert any("USING hnsw" in s for s in statements)


def test_split_drops_comment_only_input():
    assert split_statements("-- just a comment\n\n") == []
