"""Settings > Scanned attachments (specs/features/signature-detection.md)."""

import pytest

from app import scan_reading_routes
from app.scan_reading_routes import ScanReading
from tests.test_account import _signed_in, calls  # noqa: F401  (fixture)

CLIENT = {"X-AIMail-Client": "1"}


@pytest.fixture
def stored(monkeypatch):
    """The user's saved choice, kept in memory instead of the database."""
    state = {"mode": None, "audits": []}

    async def chosen(_user_id):
        return state["mode"] or ScanReading.LOCAL

    async def save(_user_id, mode):
        state["mode"] = mode

    async def audit(action, **fields):
        state["audits"].append((action, fields["mode"]))

    monkeypatch.setattr(scan_reading_routes, "_chosen", chosen)
    monkeypatch.setattr(scan_reading_routes, "_save", save)
    monkeypatch.setattr(scan_reading_routes, "audit", audit)
    return state


def test_a_user_who_never_chose_reads_scans_locally(calls, stored, monkeypatch):  # noqa: F811
    monkeypatch.setattr(scan_reading_routes, "is_check_offered", lambda: True)
    assert _signed_in().get("/settings/scan-reading").json() == {"available": True, "mode": "local"}


def test_checked_scans_cannot_be_chosen_without_a_local_vision_model(calls, stored, monkeypatch):  # noqa: F811
    monkeypatch.setattr(scan_reading_routes, "is_check_offered", lambda: False)
    response = _signed_in().put("/settings/scan-reading", json={"mode": "checked"}, headers=CLIENT)
    assert response.status_code == 409 and response.json()["error"]["code"] == "scan_check_unavailable"
    assert stored["mode"] is None


def test_checked_scans_are_saved_and_audited_where_offered(calls, stored, monkeypatch):  # noqa: F811
    monkeypatch.setattr(scan_reading_routes, "is_check_offered", lambda: True)
    response = _signed_in().put("/settings/scan-reading", json={"mode": "checked"}, headers=CLIENT)
    assert response.json() == {"available": True, "mode": "checked"}
    assert stored["mode"] == ScanReading.CHECKED and stored["audits"][0][1] == "checked"


def test_going_back_to_local_is_allowed_even_where_the_check_was_removed(calls, stored, monkeypatch):  # noqa: F811
    stored["mode"] = ScanReading.CHECKED
    monkeypatch.setattr(scan_reading_routes, "is_check_offered", lambda: False)
    response = _signed_in().put("/settings/scan-reading", json={"mode": "local"}, headers=CLIENT)
    assert response.status_code == 200 and stored["mode"] == ScanReading.LOCAL


def test_an_unknown_mode_is_refused(calls, stored):  # noqa: F811
    response = _signed_in().put("/settings/scan-reading", json={"mode": "cloud"}, headers=CLIENT)
    assert response.status_code == 422
