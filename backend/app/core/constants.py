"""Pinned, cross-module constants. Single source of truth for the embedding contract."""

# gemini-embedding-001 @ 1536 dims is pinned by pgvector's 2000-dim HNSW cap.
# See docs/decisions/lane-b-ml.md. Changing the dim needs a migration + full re-embed.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536

# Answer-generation model for the /ask demo. Override via the GEMINI_CHAT_MODEL env var.
# If a call returns "model not found", swap this (e.g. gemini-flash-latest, gemini-3.6-flash).
CHAT_MODEL = "gemini-2.5-flash"
