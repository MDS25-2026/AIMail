"""Pinned, cross-module constants. Single source of truth for the embedding contract."""

# gemini-embedding-001 @ 1536 dims is pinned by pgvector's 2000-dim HNSW cap.
# See docs/decisions/lane-b-ml.md. Changing the dim needs a migration + full re-embed.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536

# Answer-generation model for the /ask demo. Override via the GEMINI_CHAT_MODEL env var.
# If a call returns "model not found", swap this (e.g. gemini-flash-latest, gemini-3.6-flash).
CHAT_MODEL = "gemini-2.5-flash"

# Ingestion input limits (OWASP API8: unbounded reads are a denial-of-service surface).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — comfortably above a real policy PDF
UPLOAD_CHUNK_BYTES = 64 * 1024  # streamed so an oversized file is rejected before it is buffered
MAX_PASTE_CHARS = 200_000  # ~50k tokens; the paste path has no file size to bound it
PDF_MAGIC = b"%PDF-"  # a .pdf extension is a claim; the header is evidence

# Size caps stop one huge upload; this stops many small ones. Generous enough that a human
# uploading a folder of policy PDFs never trips it.
INGEST_RATE_LIMIT = 20
INGEST_RATE_WINDOW_SECONDS = 60
