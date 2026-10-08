"""Errors shared by the embedders and their callers, apart so the model registry can raise them too."""


class EmbeddingError(RuntimeError):
    """The embedding model could not be reached, or returned vectors the database cannot hold."""
