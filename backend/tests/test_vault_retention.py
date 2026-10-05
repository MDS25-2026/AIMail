"""Detail vaults are emptied once a reply is unlikely to still be written."""

from sqlalchemy.dialects import postgresql

from app.vault_retention import SENT_RETENTION_DAYS, expired


def test_a_vault_expires_after_the_retention_period_or_a_week_after_its_reply_whichever_is_first():
    sql = str(expired(30).compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "messages.pii_vault IS NOT NULL" in sql
    assert f"messages.created_at < now() - make_interval(secs=>{30 * 86400}.0)" in sql
    assert f"messages.sent_at < now() - make_interval(secs=>{SENT_RETENTION_DAYS * 86400}.0)" in sql
    assert " OR " in sql
