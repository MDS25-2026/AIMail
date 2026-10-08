"""An opaque position in a newest-first list: the last row's (created_at, id), so a page never skips or
repeats a row when new ones arrive (keyset, not offset). Clients pass it back unread."""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.errors import DomainError, ErrorCode

_SEPARATOR = "|"


@dataclass(frozen=True)
class Cursor:
    created_at: datetime
    row_id: UUID

    def encode(self) -> str:
        raw = f"{self.created_at.isoformat()}{_SEPARATOR}{self.row_id}"
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_cursor(text: str) -> Cursor:
    try:
        raw = base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()
        created_at, row_id = raw.split(_SEPARATOR)
        return Cursor(datetime.fromisoformat(created_at), UUID(row_id))
    except (binascii.Error, UnicodeDecodeError, ValueError) as error:
        raise DomainError(ErrorCode.INVALID_REQUEST, "not a cursor this API issued") from error
