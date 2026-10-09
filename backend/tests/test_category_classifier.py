"""Unit tests for the 6-category B2B email taxonomy classifier (#141)."""

import time

from app.contracts import DashboardEmail
from app.db.models import AuthStatus
from app.ml.category import CATEGORY_DISPLAY_NAMES, EmailCategory, predict_category


def test_category_enum_values():
    """Verify all 6 required taxonomy categories are defined and distinct."""
    expected_categories = {"client", "vendor", "internal", "security", "admin", "personal"}
    actual_categories = {c.value for c in EmailCategory}
    assert actual_categories == expected_categories
    assert len(CATEGORY_DISPLAY_NAMES) == 6


def test_predict_category_graceful_fallbacks():
    """Verify empty, whitespace, and short stub bodies do not raise unhandled errors."""
    cat, conf = predict_category("")
    assert cat == EmailCategory.INTERNAL
    assert conf == 0.0

    cat, conf = predict_category("   \n\t  ")
    assert cat == EmailCategory.INTERNAL
    assert conf == 0.0

    cat, conf = predict_category("Hello")
    assert cat == EmailCategory.INTERNAL
    assert conf == 0.0


def test_dashboard_email_contract_supports_category():
    """Verify DashboardEmail schema includes category and categoryConfidence."""
    email_data = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "sender": "partner@vendor.com",
        "subject": "SaaS Subscription Renewal",
        "preview": "Your annual renewal is due...",
        "body": "Your annual renewal is due next month.",
        "timestamp": "2026-10-08T12:00:00Z",
        "authStatus": AuthStatus.PASS,
        "priority": "high",
        "category": "vendor",
        "categoryConfidence": 0.942,
        "threadContext": [],
        "aiSummary": "Vendor renewal notice",
        "actionItems": ["Review invoice"],
        "draftReply": "Thanks, will process.",
        "tone": "professional",
        "sources": [],
        "piiMasked": True,
        "criticConfidence": 0.88,
    }
    dashboard_email = DashboardEmail(**email_data)
    assert dashboard_email.category == "vendor"
    assert dashboard_email.categoryConfidence == 0.942


def test_inference_latency_budget():
    """Verify category classification completes comfortably within the <50ms SLA gate."""
    sample_email = (
        "Subject: SOC 2 Type II Audit Evidence Request\n\n"
        "Hi [PERSON_1],\n\n"
        "Our compliance team at [ORG_1] is completing our annual SOC 2 audit. "
        "Please provide the latest access control policy and evidence of encryption keys rotation. "
        "We need this signed off by [DATE_1].\n\n"
        "Best regards,\n[PERSON_2]"
    )
    # Warm up cached model artifact
    predict_category("Warm up model")

    start = time.perf_counter()
    cat, conf = predict_category(sample_email)
    elapsed_ms = (time.perf_counter() - start) * 1000

    # CPU inference must execute in < 50ms
    assert elapsed_ms < 50.0
    assert isinstance(cat, EmailCategory)
    assert 0.0 <= conf <= 1.0
