"""Erasure (app/erasure.py): every owned table is covered, and each subject erases what it should."""

import asyncio
from uuid import uuid4

from sqlalchemy.dialects import postgresql

import app.db.models  # noqa: F401  (registers every table)
from app.db.base import Base
from app.erasure import RETAINED, RULES, Subject, erase


def _owned_tables() -> set[str]:
    return {table.name for table in Base.metadata.sorted_tables if "user_id" in table.columns} | {"user_profile"}


def test_every_table_that_holds_user_data_is_erased_or_retained_with_a_reason():
    covered = {rule.table.__tablename__ for rule in RULES[Subject.ACCOUNT]} | set(RETAINED)
    assert _owned_tables() - covered == set()


def test_disconnecting_keeps_what_did_not_come_from_the_mailbox():
    erased = {rule.table.__tablename__ for rule in RULES[Subject.MAILBOX]}
    assert {"writing_style", "user_preferences", "holding_reply_settings", "user_profile"}.isdisjoint(erased)
    assert {"messages", "mailbox_connection", "style_habit", "holding_reply"} <= erased


def test_deleting_the_account_includes_everything_disconnecting_does():
    assert set(RULES[Subject.MAILBOX]) <= set(RULES[Subject.ACCOUNT])


class _Session:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(str(statement.compile(dialect=postgresql.dialect(),
                                                     compile_kwargs={"literal_binds": True})))
        return type("Result", (), {"rowcount": 1})()


def test_a_disconnect_takes_only_sent_replies_and_examples_taken_from_sends():
    session = _Session()
    counts = asyncio.run(erase(session, uuid4(), Subject.MAILBOX))
    document = next(sql for sql in session.statements if sql.startswith("DELETE FROM document"))
    example = next(sql for sql in session.statements if sql.startswith("DELETE FROM style_example"))
    assert "doc_type = 'sent_reply'" in document and "source = 'sent'" in example
    assert counts["messages"] == 1


def test_rows_that_point_at_others_are_erased_first():
    session = _Session()
    asyncio.run(erase(session, uuid4(), Subject.ACCOUNT))
    tables = [sql.split()[2] for sql in session.statements]
    assert tables.index("holding_reply") < tables.index("messages") < tables.index("user_profile")
