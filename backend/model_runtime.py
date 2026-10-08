"""What every model client shares, whichever provider answers (specs/features/local-model.md).

One error type with one set of codes, one time budget per request, and one record of every attempt, so
Gemini and the local model are held to the same contract and the agent handles them the same way.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from enum import StrEnum

from app.core.config import get_settings

# Below the dashboard's AGENT_TIMEOUT_SECONDS (app/dashboard.py), with room for retrieval first.
DEFAULT_DEADLINE_SECONDS = 100.0

OUTCOME_OK = "ok"
OUTCOME_TRANSPORT_ERROR = "transport_error"
OUTCOME_CIRCUIT_OPEN = "circuit_open"


class ModelErrorCode(StrEnum):
    # The values predate Private mode and are stored as review reasons; they name the failure, whichever
    # provider had it.
    UNAVAILABLE = "gemini_unavailable"
    DEADLINE_EXCEEDED = "gemini_deadline_exceeded"
    OUTPUT_TRUNCATED = "gemini_output_truncated"
    NO_CANDIDATE = "gemini_no_candidate"
    MALFORMED_JSON = "gemini_malformed_json"
    # The request itself was refused (400/413/422): another try or another model will not help.
    REJECTED = "gemini_rejected"


# Outcomes about the content, not the provider: retrying at temperature 0 gives the same answer.
CONTENT_ERRORS = frozenset({
    ModelErrorCode.OUTPUT_TRUNCATED, ModelErrorCode.NO_CANDIDATE,
    ModelErrorCode.MALFORMED_JSON, ModelErrorCode.REJECTED,
})


class ModelError(RuntimeError):
    def __init__(self, code: ModelErrorCode, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


@dataclass(frozen=True)
class ModelCall:
    """One attempt, kept per draft so a slow or rescued draft shows why."""

    model: str
    outcome: str  # "ok", "http_<status>", "transport_error", "circuit_open" or "truncated"
    ms: int
    provider: str = "gemini"


_deadline: ContextVar[float | None] = ContextVar("model_deadline", default=None)
_calls: ContextVar[list[ModelCall] | None] = ContextVar("model_calls", default=None)


@contextmanager
def track_calls() -> Iterator[list[dict]]:
    """Collect every attempt made inside the block, as JSON-ready dicts once it exits."""
    calls: list[ModelCall] = []
    report: list[dict] = []
    token = _calls.set(calls)
    try:
        yield report
    finally:
        _calls.reset(token)
        report.extend(asdict(call) for call in calls)


def record_call(model: str, outcome: str, started: float, provider: str = "gemini") -> None:
    calls = _calls.get()
    if calls is not None:
        calls.append(ModelCall(model, outcome, round((time.monotonic() - started) * 1000), provider))


@contextmanager
def deadline(seconds: float | None = None) -> Iterator[None]:
    """Every model call inside this block shares one time budget."""
    budget = seconds if seconds is not None else _configured_deadline()
    token = _deadline.set(time.monotonic() + budget)
    try:
        yield
    finally:
        _deadline.reset(token)


def _configured_deadline() -> float:
    value = get_settings().agent_deadline_seconds
    return value if value > 0 else DEFAULT_DEADLINE_SECONDS


def remaining_seconds() -> float:
    end = _deadline.get()
    return math.inf if end is None else end - time.monotonic()
