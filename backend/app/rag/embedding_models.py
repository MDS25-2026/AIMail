"""Which embedding model each provider uses, how wide its vectors are, and where they are stored.

The width is fixed by the database column (vector(n)), not by a setting: changing it needs a
migration and a full re-embed. So it is checked twice, at startup against the column, and on every
batch against what the model returned. A swapped local model fails with its name and both widths,
not as an opaque insert error halfway through a re-embed.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import MisconfiguredError, get_settings
from app.core.constants import EMBEDDING_DIM, EMBEDDING_MODEL, LOCAL_EMBEDDING_DIM
from app.core.providers import Provider
from app.db.session import get_engine
from app.rag.errors import EmbeddingError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbeddingModel:
    table: str
    dimensions: int


REGISTRY: dict[Provider, EmbeddingModel] = {
    Provider.GEMINI: EmbeddingModel(table="embedding", dimensions=EMBEDDING_DIM),
    Provider.LOCAL: EmbeddingModel(table="local_embedding", dimensions=LOCAL_EMBEDDING_DIM),
}
GEMINI_MODEL_NAME = EMBEDDING_MODEL

_COLUMN_TYPE = text("""
    SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
    JOIN pg_class c ON c.oid = a.attrelid JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname = :table AND a.attname = 'embedding' AND NOT a.attisdropped""")


def checked(vectors: list[list[float]], provider: Provider, model: str) -> list[list[float]]:
    expected = REGISTRY[provider].dimensions
    widths = {len(vector) for vector in vectors}
    if widths - {expected}:
        raise EmbeddingError(f"{model} returned vectors of width {sorted(widths)}, but the "
                             f"{REGISTRY[provider].table} column holds {expected}: re-embedding needs a migration")
    return vectors


async def check_columns() -> None:
    """Refuse to start when a column's width differs from the registry; a database that cannot be
    reached, or is not configured, is left to the readiness probe, which reports it."""
    if not get_settings().database_url:
        logger.warning("embedding columns not checked: DATABASE_URL is not set")
        return
    try:
        async with get_engine().connect() as connection:
            for provider, model in REGISTRY.items():
                column = await connection.scalar(_COLUMN_TYPE, {"table": model.table})
                if column != f"vector({model.dimensions})":
                    raise MisconfiguredError(f"{model.table}.embedding is {column}, but {provider} "
                                             f"embeddings are vector({model.dimensions})")
    except (SQLAlchemyError, OSError) as error:
        logger.warning("embedding columns not checked, the database did not answer: %s", error)
