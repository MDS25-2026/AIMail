"""FastAPI entrypoint.

Serves the Lane B retrieval demo: search (POST /search), the knowledge-base inventory
(GET /documents), and two write paths - paste text (POST /documents) and PDF upload
(POST /documents/upload). These are DEMO endpoints, not the finalized REST contract;
that belongs in specs/context/api-contracts.md with Lane D.
"""

import asyncio
import logging
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import InterfaceError, OperationalError

from app.contracts import DashboardEmail
from app.core.auth import require_auth
from app.core.config import get_settings
from app.core.constants import (
    MAX_PASTE_CHARS,
    MAX_UPLOAD_BYTES,
    PDF_MAGIC,
    UPLOAD_CHUNK_BYTES,
)
from app.core.ratelimit import rate_limit_ingest
from app.dashboard import (
    approve_and_send,
    email_detail,
    generate_pending,
    list_dashboard_emails,
    refine_email,
    regenerate_email,
)
from app.gmail_send import SendError
from app.rag.chunk import extract_pdf_bytes
from app.rag.embed import EmbeddingError
from app.rag.generate import GenerationError, answer
from app.rag.ingest import ingest_text
from app.rag.library import DocumentSummary, list_documents
from app.rag.retrieve import ContextChunk, retrieve

app = FastAPI(title="AImail backend", dependencies=[Depends(require_auth)])

# Dev CORS so the Next.js frontend can call this API cross-origin. The regex covers any
# localhost/127.0.0.1 port (they are distinct origins to the browser); FRONTEND_ORIGIN adds
# an explicit non-local origin for a real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATIC = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)

_pregen_task: asyncio.Task | None = None


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


@app.on_event("startup")
async def _start_pregen() -> None:
    if get_settings().auto_generate:
        global _pregen_task
        _pregen_task = asyncio.create_task(_pregen_loop())


@app.on_event("shutdown")
async def _stop_pregen() -> None:
    if _pregen_task is not None:
        _pregen_task.cancel()


async def _database_unreachable(request: Request, exc: Exception) -> JSONResponse:
    # DB connection failures (raw OSError / SQLAlchemy connect errors) become a clean 503 instead
    # of a raw 500 stack trace — usually a wrong DATABASE_URL or a paused Supabase project.
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "DATABASE_UNREACHABLE",
                "message": (
                    "Cannot reach the database. Check DATABASE_URL (use the Supabase Session "
                    "pooler, not the direct IPv6 host) and that the Supabase project is not paused."
                ),
            }
        },
    )


for _db_exc in (OSError, OperationalError, InterfaceError):
    app.add_exception_handler(_db_exc, _database_unreachable)


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


@app.post("/search")
async def search(request: SearchRequest) -> list[ContextChunk]:
    return await retrieve(request.query, request.k)


@app.post("/ask")
async def ask(request: AskRequest) -> AskResponse:
    # Full RAG loop demo: retrieve policy chunks, then generate a grounded answer from them.
    chunks = await retrieve(request.question, request.k)
    text = await answer(request.question, chunks)
    return AskResponse(answer=text, sources=chunks)


@app.get("/emails")
async def emails() -> list[DashboardEmail]:
    # Fast list: Han's Email shape from ingested messages + Lane B priority (no generation).
    return await list_dashboard_emails()


@app.get("/emails/{message_id}")
async def email_detail_route(message_id: str) -> DashboardEmail:
    # Detail view: adds Lane C generation (retrieve + /process-email) for one opened email.
    email = await email_detail(message_id)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class RegenerateRequest(BaseModel):
    tone: str = "professional"  # "professional" | "casual"


@app.post("/emails/{message_id}/regenerate")
async def regenerate_email_route(
    message_id: str, body: RegenerateRequest | None = None
) -> DashboardEmail:
    # Force a fresh draft in the requested tone (Regenerate button / tone toggle). Body optional.
    email = await regenerate_email(message_id, body.tone if body else "professional")
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class RefineRequest(BaseModel):
    instruction: str  # e.g. "make it shorter", "add a deadline"
    draft: str  # the current draft to revise


@app.post("/emails/{message_id}/refine")
async def refine_email_route(message_id: str, body: RefineRequest) -> DashboardEmail:
    # Revise the current draft per the user's instruction (dashboard's Refine box).
    email = await refine_email(message_id, body.instruction, body.draft)
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class SendRequest(BaseModel):
    draft: str  # the approved, possibly edited draft body to send


@app.post("/emails/{message_id}/send")
async def send_email_route(message_id: str, body: SendRequest) -> DashboardEmail:
    # Human-approved send: reply to the original sender with the draft, then mark it sent.
    try:
        email = await approve_and_send(message_id, body.draft)
    except SendError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"send failed: {exc}") from exc
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
