"""A vector the database cannot hold is refused by name before it is stored."""

import pytest

from app.core.constants import LOCAL_EMBEDDING_DIM
from app.core.providers import Provider
from app.rag.embedding_models import REGISTRY, checked
from app.rag.errors import EmbeddingError


def test_vectors_of_the_columns_width_pass_through():
    vectors = [[0.0] * LOCAL_EMBEDDING_DIM]
    assert checked(vectors, Provider.LOCAL, "embeddinggemma") is vectors


def test_a_swapped_local_model_is_named_with_both_widths():
    with pytest.raises(EmbeddingError, match=r"mxbai-embed-large.*\[1024\].*768"):
        checked([[0.0] * 1024], Provider.LOCAL, "mxbai-embed-large")


def test_every_provider_has_a_registered_model():
    assert set(REGISTRY) == set(Provider)
