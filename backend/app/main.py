"""FastAPI entrypoint.

Serves the Lane B retrieval demo: search (POST /search), the knowledge-base inventory
(GET /documents), and two write paths - paste text (POST /documents) and PDF upload
(POST /documents/upload). These are DEMO endpoints, not the finalized REST contract;
that belongs in specs/context/api-contracts.md with Lane D.
"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.admin.app import admin_app
from app.contracts import DashboardEmail
from app.core.auth import require_auth
from app.core.config import get_settings
from app.core.constants import (
    ADMIN_PREFIX,
    DEFAULT_ADMIN_ORIGINS,
    MAX_DRAFT_CHARS,
    MAX_PASTE_CHARS,
    MAX_UPLOAD_BYTES,
    PDF_MAGIC,
    UPLOAD_CHUNK_BYTES,
)
from app.core.cors import PathScopedCORS, origins_from
from app.core.db_errors import register_database_handlers
from app.core.logging_setup import configure_logging
from app.core.middleware import request_context
from app.core.ratelimit import (
    rate_limit_detail,
    rate_limit_generation,
    rate_limit_ingest,
)
from app.dashboard import (
    AlreadySentError,
    DraftNotUpdatedError,
    SendRejectedError,
    TranslationError,
    approve_and_send,
    email_detail,
    generate_pending,
    list_dashboard_emails,
    refine_email,
    regenerate_email,
    translate_email,
)
from app.gmail_send import SendError, SendOutcomeUnknownError
from app.rag.chunk import extract_pdf_bytes
from app.rag.embed import EmbeddingError
from app.rag.generate import GenerationError, answer
from app.rag.ingest import embed_pending, ingest_text
from app.rag.library import DocumentSummary, list_documents
from app.rag.retrieve import ContextChunk, retrieve

configure_logging()

@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Background work for the life of the process: embed any pending chunks once, and poll for
    drafts to pre-generate. Both are held (asyncio keeps only weak references to tasks) and both
    are cancelled on shutdown."""
    tasks = [asyncio.create_task(_embed_missing())]
    if get_settings().auto_generate:
        tasks.append(asyncio.create_task(_pregen_loop()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()


app = FastAPI(title="AImail backend", dependencies=[Depends(require_auth)], lifespan=_lifespan)
app.middleware("http")(request_context)
# Its own app, so the shared token never applies there: admin is a Supabase session (ADR 0004).
app.mount(ADMIN_PREFIX, admin_app)

# Dev CORS so the dashboard can call this API cross-origin. The regex covers any
# localhost/127.0.0.1 port (they are distinct origins to the browser); FRONTEND_ORIGIN adds
# an explicit non-local origin for a real deployment. Admin paths get their own, credentialed
# policy for ADMIN_ORIGINS only (app/core/cors.py, ADR 0004).
app.add_middleware(
    PathScopedCORS,
    admin_prefix=ADMIN_PREFIX,
    admin_origins=origins_from(os.environ.get("ADMIN_ORIGINS", DEFAULT_ADMIN_ORIGINS)),
    public_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
    public_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
)

_STATIC = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)



async def _pregen_loop() -> None:
    """Periodically pre-generate drafts for new messages so opening them is instant."""
    poll = get_settings().generate_poll_seconds
    while True:
        try:
            await asyncio.sleep(poll)
            # Small batch per cycle so the ~6-calls-per-email pipeline stays under the Gemini
            # free-tier rate limit instead of bursting the whole backlog at once.
            count = await generate_pending(limit=2)
            if count:
                logger.info("pre-generated %d draft(s)", count)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("pre-generation poll failed")


async def _embed_missing() -> None:
    """Chunks without a vector under the current EMBEDDING_TAG get one. Free when none are
    pending; after a tag bump or on a fresh database it stops retrieval silently returning nothing."""
    try:
        count = await embed_pending()
    except Exception:
        logger.exception("startup embedding of pending chunks failed; retrieval may be empty")
        return
    if count:
        logger.info("embedded %d pending chunk(s) under the current tag", count)




register_database_handlers(app)


async def _ai_service_unreachable(request: Request, exc: Exception) -> JSONResponse:
    # Gemini embedding/generation failures become a clean 503 instead of a raw 500.
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "AI_SERVICE_UNREACHABLE",
                "message": "Cannot reach the Gemini AI service - check GEMINI_API_KEY and connectivity.",
            }
        },
    )


for _ai_exc in (EmbeddingError, GenerationError):
    app.add_exception_handler(_ai_exc, _ai_service_unreachable)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class DocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    # Capped for the same reason as the upload path: this is the other unbounded ingestion input.
    text: str = Field(min_length=1, max_length=MAX_PASTE_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    sources: list[ContextChunk]


@app.get("/")
async def demo_page() -> FileResponse:
    return FileResponse(_STATIC / "demo.html")


@app.post("/search", dependencies=[Depends(rate_limit_generation)])
async def search(request: SearchRequest) -> list[ContextChunk]:
    return await retrieve(request.query, request.k)


@app.post("/ask", dependencies=[Depends(rate_limit_generation)])
async def ask(request: AskRequest) -> AskResponse:
    # Full RAG loop demo: retrieve policy chunks, then generate a grounded answer from them.
    chunks = await retrieve(request.question, request.k)
    text = await answer(request.question, chunks)
    return AskResponse(answer=text, sources=chunks)


@app.get("/emails")
async def emails() -> list[DashboardEmail]:
    # Fast list: Han's Email shape from ingested messages + Lane B priority (no generation).
    return await list_dashboard_emails()


@app.get("/emails/{message_id}", dependencies=[Depends(rate_limit_detail)])
async def email_detail_route(message_id: str) -> DashboardEmail:
    # Detail view: adds Lane C generation (retrieve + /process-email) for one opened email.
    email = await email_detail(message_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class RegenerateRequest(BaseModel):
    tone: str = "professional"  # "professional" | "casual"


@app.post("/emails/{message_id}/regenerate", dependencies=[Depends(rate_limit_generation)])
async def regenerate_email_route(
    message_id: str, body: RegenerateRequest | None = None
) -> DashboardEmail:
    # Force a fresh draft in the requested tone (Regenerate button / tone toggle). Body optional.
    try:
        email = await regenerate_email(message_id, body.tone if body else "professional")
    except AlreadySentError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_sent") from exc
    except DraftNotUpdatedError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class RefineRequest(BaseModel):
    instruction: str  # e.g. "make it shorter", "add a deadline"
    draft: str  # the current draft to revise


@app.post("/emails/{message_id}/refine", dependencies=[Depends(rate_limit_generation)])
async def refine_email_route(message_id: str, body: RefineRequest) -> DashboardEmail:
    # Revise the current draft per the user's instruction (dashboard's Refine box).
    try:
        email = await refine_email(message_id, body.instruction, body.draft)
    except AlreadySentError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "already_sent") from exc
    except DraftNotUpdatedError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class TranslateRequest(BaseModel):
    language: Literal["en", "ms", "zh"]


class TranslateResponse(BaseModel):
    language: str
    text: str


@app.post(
    "/emails/{message_id}/translate", dependencies=[Depends(rate_limit_generation)]
)
async def translate_email_route(message_id: str, body: TranslateRequest) -> TranslateResponse:
    # The masked body in the reader's language; refused (422) if the result is unfaithful.
    try:
        translated = await translate_email(message_id, body.language)
    except TranslationError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    if translated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return TranslateResponse(**translated)


class SendRequest(BaseModel):
    draft: str = Field(min_length=1, max_length=MAX_DRAFT_CHARS)  # the approved, possibly edited draft


@app.post("/emails/{message_id}/send")
async def send_email_route(message_id: str, body: SendRequest) -> DashboardEmail:
    # Human-approved send: reply to the original sender with the draft, then mark it sent.
    try:
        email = await approve_and_send(message_id, body.draft)
    except SendRejectedError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    except SendOutcomeUnknownError as exc:
        logger.warning("send outcome unknown for %s: %s", message_id, exc)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "send_outcome_unknown") from exc
    except SendError as exc:
        # The reason stays in the log: it can name local credential paths.
        logger.warning("send failed for %s: %s", message_id, exc)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "send_failed") from exc
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class SystemInfo(BaseModel):
    """Non-secret runtime configuration for the dashboard's Settings view.

    Model names and feature flags only — never keys, URLs, or credentials, since this is
    served to the browser.
    """

    chat_model: str
    embedding_model: str
    embedding_dim: int
    priority_model: str
    auth_enabled: bool
    auto_generate: bool
    generate_poll_seconds: int
    document_count: int
    chunk_count: int


@app.get("/system/info")
async def system_info() -> SystemInfo:
    settings = get_settings()
    documents = await list_documents()
    return SystemInfo(
        chat_model=settings.gemini_chat_model,
        embedding_model=settings.embedding_model,
        embedding_dim=settings.embedding_dim,
        priority_model=settings.priority_model,
        auth_enabled=bool(settings.backend_api_token),
        auto_generate=settings.auto_generate,
        generate_poll_seconds=settings.generate_poll_seconds,
        document_count=len(documents),
        chunk_count=sum(d["chunk_count"] for d in documents),
    )


@app.get("/documents")
async def get_documents() -> list[DocumentSummary]:
    return await list_documents()


@app.post("/documents", dependencies=[Depends(rate_limit_ingest)])
async def add_document(request: DocumentRequest) -> dict[str, int]:
    # Interim persist path: paste text -> chunk/embed/store.
    count = await ingest_text(f"paste://{request.title}", request.title, request.text)
    return {"chunks": count}


async def _read_capped(file: UploadFile) -> bytes:
    """Stream the upload, aborting past MAX_UPLOAD_BYTES so a huge file is never buffered whole."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/documents/upload", dependencies=[Depends(rate_limit_ingest)])
async def upload_document(file: UploadFile) -> dict[str, int]:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only .pdf files are supported")
    data = await _read_capped(file)
    if not data.startswith(PDF_MAGIC):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "file is not a PDF (the .pdf extension does not match its contents)",
        )
    try:
        text = extract_pdf_bytes(data)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "could not read the PDF") from exc
    count = await ingest_text(f"upload://{filename}", filename, text)
    return {"chunks": count}
