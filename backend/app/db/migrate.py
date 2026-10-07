"""Apply raw SQL migration files to the configured database."""

from pathlib import Path

from sqlalchemy import text

from app.db.session import get_engine


def split_statements(sql: str) -> list[str]:
    """Split a migration into individual statements, dropping full-line comments."""
    body = "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("--")
    )
    if "$$" not in body:
        return [stmt.strip() for stmt in body.split(";") if stmt.strip()]

    statements: list[str] = []
    current: list[str] = []
    in_dollar_quote = False
    for token in body.split(";"):
        current.append(token)
        if token.count("$$") % 2 != 0:
            in_dollar_quote = not in_dollar_quote
        if not in_dollar_quote:
            stmt = ";".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
    if current:
        stmt = ";".join(current).strip()
        if stmt:
            statements.append(stmt)
    return statements


async def apply_sql_file(path: Path) -> int:
    """Run every statement in a .sql file in one transaction. Returns the statement count."""
    statements = split_statements(path.read_text())
    engine = get_engine()
    async with engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))
    return len(statements)
