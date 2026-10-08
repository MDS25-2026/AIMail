"""The inbox cursor is opaque to clients and refused when it is not one this API issued."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.core.cursor import Cursor, decode_cursor
from app.core.errors import DomainError, ErrorCode


def test_a_cursor_round_trips():
    cursor = Cursor(datetime(2026, 10, 8, 9, 30, 15, 123456, tzinfo=timezone.utc), uuid4())
    assert decode_cursor(cursor.encode()) == cursor


@pytest.mark.parametrize("text", ["", "not-base64!", "aGVsbG8", "MjAyNi0xMC0wOHxub3QtYS11dWlk"])
def test_a_cursor_this_api_did_not_issue_is_an_invalid_request(text):
    with pytest.raises(DomainError) as refused:
        decode_cursor(text)
    assert refused.value.code == ErrorCode.INVALID_REQUEST


def test_the_page_size_is_bounded(api_client):
    response = api_client.get("/emails?limit=1000", headers={"Authorization": "Bearer test-token-not-a-real-secret"})
    assert response.status_code == 422
