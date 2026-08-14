import numpy as np

from app.rag.embed import _l2_normalize


def test_normalizes_to_unit_length():
    out = _l2_normalize(np.array([[3.0, 4.0]]))
    assert np.allclose(out, [[0.6, 0.8]])
    assert np.isclose(np.linalg.norm(out[0]), 1.0)


def test_zero_vector_stays_zero_without_nan():
    out = _l2_normalize(np.array([[0.0, 0.0]]))
    assert not np.isnan(out).any()
    assert np.allclose(out, [[0.0, 0.0]])
