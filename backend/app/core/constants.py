"""Pinned, cross-module constants. Single source of truth for the embedding contract."""

# gemini-embedding-001 @ 1536 dims is pinned by pgvector's 2000-dim HNSW cap.
# See docs/decisions/lane-b-ml.md. Changing the dim needs a migration + full re-embed.
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536
# Stored in embedding.model_name. It names the model AND how its vectors were made: chunks are
# embedded as RETRIEVAL_DOCUMENT and queries as RETRIEVAL_QUERY, and a vector of one kind is not
# comparable with the other. Bump it whenever that changes; embed_pending re-embeds under the new
# tag, and the old rows stay so a rollback is a one-line change.
EMBEDDING_TAG = f"{EMBEDDING_MODEL}/retrieval-task"
# Private mode's local embedding model (embeddinggemma); its vectors live in local_embedding.
LOCAL_EMBEDDING_DIM = 768
# How often pending chunks are embedded, so switching Private mode on or off catches up by itself.
EMBED_POLL_SECONDS = 60

# Answer-generation model for the /ask demo. Override via the GEMINI_CHAT_MODEL env var.
# If a call returns "model not found", swap this (e.g. gemini-flash-latest, gemini-3.6-flash).
CHAT_MODEL = "gemini-2.5-flash"

# Ingestion input limits (OWASP API8: unbounded reads are a denial-of-service surface).
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — comfortably above a real policy PDF
UPLOAD_CHUNK_BYTES = 64 * 1024  # streamed so an oversized file is rejected before it is buffered
MAX_PASTE_CHARS = 200_000  # ~50k tokens; the paste path has no file size to bound it
MAX_DRAFT_CHARS = 20_000  # a reply, not a document; generous for a long email
PDF_MAGIC = b"%PDF-"  # a .pdf extension is a claim; the header is evidence

# Size caps stop one huge upload; this stops many small ones. Generous enough that a human
# uploading a folder of policy PDFs never trips it.
INGEST_RATE_LIMIT = 20
INGEST_RATE_WINDOW_SECONDS = 60
# Each request on these routes costs Gemini calls (a regenerate is ~6). Ten a minute is far above
# a person clicking and far below what drains the free tier.
GENERATION_RATE_LIMIT = 10
GENERATION_RATE_WINDOW_SECONDS = 60
# Across every user: the model quota is the project's, so many users at once must not exhaust it.
GLOBAL_GENERATION_RATE_LIMIT = 60
DETAIL_RATE_LIMIT = 60
DETAIL_RATE_WINDOW_SECONDS = 60
# Password guessing on the admin sign-in: five tries per five minutes per client, on top of
# Supabase's own limits.
ADMIN_SIGN_IN_LIMIT = 5
ADMIN_SIGN_IN_WINDOW_SECONDS = 300

# Admin console (docs/adr/0004). The dashboard as `make web` serves it; set ADMIN_ORIGINS for any
# other host or port. Only these origins may carry the admin session cross-origin.
ADMIN_PREFIX = "/admin"
# localhost only: from 127.0.0.1 the dashboard and an API on localhost are different sites, and
# the SameSite=Strict session cookie would not travel anyway. Open the dashboard at localhost.
DEFAULT_ADMIN_ORIGINS = "http://localhost:8090"

# Holding replies (specs/features/holding-reply.md): product behaviour, not deployment config.
# The wait before sending, so the user can still answer first.
HOLD_WINDOW_MINUTES = 10
# A reply not sent within this long after it fell due is cancelled: a day-late "I'll get back to
# you" is worse than none.
HOLDING_REPLY_STALE_MINUTES = 20
HOLDING_REPLY_DAILY_CAP = 50
HOLDING_REPLY_POLL_SECONDS = 60
