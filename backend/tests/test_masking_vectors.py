"""The shared floor cases (listener/testdata/masking_vectors.json): the listener's maskPII passes the same file."""

import json
from pathlib import Path

import pytest

from app.core.typed_text import mask_typed_text

_VECTORS = json.loads((Path(__file__).resolve().parents[2] / "listener" / "testdata" /
                       "masking_vectors.json").read_text())


@pytest.mark.parametrize("case", _VECTORS["must_mask"], ids=lambda case: case["kind"])
def test_the_shared_floor_cases_are_masked(case):
    assert case["secret"] not in mask_typed_text(case["text"])


@pytest.mark.parametrize("case", _VECTORS["must_keep"], ids=lambda case: case["kind"])
def test_the_shared_floor_cases_that_are_not_details_are_kept(case):
    assert case["keep"] in mask_typed_text(case["text"])
