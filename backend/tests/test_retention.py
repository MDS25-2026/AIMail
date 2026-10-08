"""Retention (app/retention.py): one table of how long each kind of data is kept."""

import asyncio

from sqlalchemy.dialects import postgresql

from app import retention


def _sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_learning_pairs_holding_recipients_and_egress_expire_by_default():
    named = {policy.name: policy for policy in retention.POLICIES}
    assert all(named[name].days() > 0 for name in ("learning_pairs", "holding_reply_recipients", "model_egress"))


def test_message_content_is_kept_until_a_limit_is_configured(test_settings):
    named = {policy.name: policy for policy in retention.POLICIES}
    assert named["message_content"].days() == retention.KEEP_FOREVER


def test_clearing_message_content_keeps_the_record_but_not_the_words():
    sql = _sql(retention._message_content(180))
    assert sql.startswith("UPDATE messages") and "body_masked" in sql and "ai_summary" in sql
    assert "DELETE" not in sql


def test_a_policy_switched_off_is_never_run(test_settings, monkeypatch):
    ran = []

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def begin(self):
            return self

        async def execute(self, statement):
            ran.append(_sql(statement).split()[1])
            return type("Result", (), {"rowcount": 2})()

    monkeypatch.setattr(retention, "get_sessionmaker", lambda: _Session)
    changed = asyncio.run(retention.apply_retention())
    assert "message_content" not in changed and changed["model_egress"] == 2
