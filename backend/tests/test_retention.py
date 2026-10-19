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
    assert "embedding=" in sql.replace(" ", "")  # the Gemini vector of the body goes with the words
    assert "subject=" in sql.replace(" ", "") and "from_addr=" in sql.replace(" ", "")
    assert "reply_to=" in sql.replace(" ", "") and "critic_checks=" in sql.replace(" ", "")
    assert "DELETE" not in sql


def test_finished_send_later_rows_expire_and_waiting_ones_stay():
    sql = _sql(retention._finished_schedules(30))
    assert sql.startswith("DELETE FROM scheduled_send")
    assert "scheduled_send.sent_at IS NOT NULL" in sql and "cancelled_reason IS NOT NULL" in sql
    named = {policy.name: policy for policy in retention.POLICIES}
    assert named["finished_scheduled_sends"].days() == retention.FINISHED_SCHEDULE_DAYS


def test_past_replies_kept_for_learning_expire_after_a_year_and_documents_stay(test_settings):
    sql = _sql(retention._past_replies(365))
    assert sql.startswith("DELETE FROM document") and "document.doc_type =" in sql
    assert retention._past_replies(365).compile().params["doc_type_1"] == "sent_reply"
    named = {policy.name: policy for policy in retention.POLICIES}
    assert named["past_replies"].days() == retention.PAST_REPLY_DAYS == 365


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
