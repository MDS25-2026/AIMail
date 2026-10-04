"""Repairing an under-masked row repairs everything derived from it, not only the body."""

from scripts.remask_outliers import repair_update

REMASKED = {"body_masked": "Hi [Redacted]", "subject": "Leave for [Redacted]",
            "snippet_masked": "Hi [Redacted]", "ai_summary": "[Redacted] asks for leave"}


def test_an_unsent_row_gets_every_masked_field_and_its_draft_cleared_to_regenerate():
    update = repair_update({"sent_at": None}, REMASKED)
    assert update["subject"] == "Leave for [Redacted]" and update["ai_summary"].startswith("[Redacted]")
    assert update["draft_reply"] is None and update["generated_at"] is None
    assert update["rag_sources"] is None and update["generation_attempts"] == 0


def test_a_sent_row_keeps_its_draft_because_it_is_the_record_of_what_went_out():
    update = repair_update({"sent_at": "2026-09-20T10:00:00Z"}, REMASKED)
    assert update["body_masked"] == "Hi [Redacted]"
    assert "draft_reply" not in update and "generated_at" not in update
