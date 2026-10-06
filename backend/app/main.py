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
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile, status
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.account_routes import router as account_router
from app.admin.app import admin_app
from app.contracts import DashboardEmail
from app.core import mailbox
from app.core.auth import (
    principal_of,
    require_auth,
    require_mailbox,
    scope_of,
    scope_of_principal,
)
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
from app.core.typed_text import mask_typed_text
from app.dashboard import (
    AlreadySentError,
    DraftNotUpdatedError,
    SendRejectedError,
    TranslationError,
    approve_and_send,
    email_detail,
    email_for_thread,
    generate_pending,
    list_dashboard_emails,
    refine_email,
    regenerate_email,
    translate_email,
)
from app.gmail_send import AccessExpiredSendError, SendError, SendOutcomeUnknownError
from app.holding_reply_routes import router as holding_reply_router
from app.holding_reply_scheduler import holding_replies_loop
from app.private_mode_routes import router as private_mode_router
from app.rag.chunk import extract_pdf_bytes
from app.rag.embed import EmbeddingError
from app.rag.generate import GenerationError, answer
from app.rag.ingest import embed_pending, ingest_text
from app.rag.library import DocumentSummary, list_documents
from app.rag.mask import DocumentMaskingError
from app.rag.retrieve import ContextChunk, retrieve
from app.sign_in import router as sign_in_router
from app.vault_retention import expire_vaults_daily
from app.writing_style_routes import router as writing_style_router

configure_logging()

@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Background work for the life of the process: embed any pending chunks once, and poll for
    drafts to pre-generate. Both are held (asyncio keeps only weak references to tasks) and both
    are cancelled on shutdown."""
    await mailbox.resolve_owner()
    tasks = [asyncio.create_task(_embed_missing()), asyncio.create_task(expire_vaults_daily()),
             asyncio.create_task(holding_replies_loop())]
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
app.include_router(sign_in_router)
app.include_router(account_router)
app.include_router(holding_reply_router)
app.include_router(private_mode_router)
app.include_router(writing_style_router)

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
                "message": "Cannot reach the Gemini AI service - check GOOGLE_API_KEY and connectivity.",
            }
        },
    )


for _ai_exc in (EmbeddingError, GenerationError):
    app.add_exception_handler(_ai_exc, _ai_service_unreachable)


@app.exception_handler(DocumentMaskingError)
async def _masking_unavailable(request: Request, exc: DocumentMaskingError) -> JSONResponse:
    # Refused, not stored unmasked: the same fail-closed rule the listener follows for email.
    logger.warning("document masking unavailable: %s", exc)
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        content={"detail": "masking_unavailable"})


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


@app.post("/search", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def search(request: SearchRequest, http: Request) -> list[ContextChunk]:
    # A typed query is embedded by Gemini, so fixed-format details are masked first.
    return await retrieve(mask_typed_text(request.query), request.k, scope=scope_of(http))


@app.post("/ask", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def ask(request: AskRequest, http: Request) -> AskResponse:
    # Full RAG loop demo: retrieve policy chunks, then generate a grounded answer from them.
    question = mask_typed_text(request.question)
    chunks = await retrieve(question, request.k, scope=scope_of(http))
    text = await answer(question, chunks)
    return AskResponse(answer=text, sources=chunks)


@app.get("/emails")
async def emails(request: Request) -> list[DashboardEmail]:
    # Fast list: Han's Email shape from ingested messages + Lane B priority (no generation).
    # Someone with no connected mailbox sees an empty inbox, not an error.
    principal = principal_of(request)
    scope = await scope_of_principal(principal)
    if scope is None:
        return []
    return await list_dashboard_emails(scope, principal.email or mailbox.owner())


@app.get("/emails/{message_id}", dependencies=[Depends(rate_limit_detail), Depends(require_mailbox)])
async def email_detail_route(message_id: str, request: Request) -> DashboardEmail:
    # Detail view: adds Lane C generation (retrieve + /process-email) for one opened email.
    email = await email_detail(message_id, scope=scope_of(request))
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


# Gmail thread ids are 16 hex digits; bounded so the path never carries anything else.
GMAIL_THREAD_ID = r"^[0-9a-f]{8,24}$"


@app.get("/emails/by-thread/{thread_id}", dependencies=[Depends(rate_limit_detail), Depends(require_mailbox)])
async def email_for_thread_route(
    thread_id: Annotated[str, PathParam(pattern=GMAIL_THREAD_ID)], request: Request
) -> DashboardEmail:
    # The Chrome extension's lookup: the email Gmail has open, by its thread.
    email = await email_for_thread(thread_id, scope=scope_of(request))
    if email is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return email


class RegenerateRequest(BaseModel):
    tone: str = "professional"  # "professional" | "casual"


@app.post("/emails/{message_id}/regenerate", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def regenerate_email_route(
    message_id: str, request: Request, body: RegenerateRequest | None = None
) -> DashboardEmail:
    # Force a fresh draft in the requested tone (Regenerate button / tone toggle). Body optional.
    try:
        email = await regenerate_email(message_id, scope=scope_of(request),
                                       tone=body.tone if body else "professional")
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


@app.post("/emails/{message_id}/refine", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def refine_email_route(message_id: str, body: RefineRequest, request: Request) -> DashboardEmail:
    # Revise the current draft per the user's instruction (dashboard's Refine box).
    try:
        email = await refine_email(message_id, body.instruction, body.draft, scope=scope_of(request))
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
    "/emails/{message_id}/translate",
    dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)],
)
async def translate_email_route(
    message_id: str, body: TranslateRequest, request: Request
) -> TranslateResponse:
    # The masked body in the reader's language; refused (422) if the result is unfaithful.
    try:
        translated = await translate_email(message_id, body.language, scope=scope_of(request))
    except TranslationError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    if translated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "email not found")
    return TranslateResponse(**translated)


class SendRequest(BaseModel):
    draft: str = Field(min_length=1, max_length=MAX_DRAFT_CHARS)  # the approved, possibly edited draft


@app.post("/emails/{message_id}/send", dependencies=[Depends(require_mailbox)])
async def send_email_route(message_id: str, body: SendRequest, request: Request) -> DashboardEmail:
    # Human-approved send: reply to the original sender with the draft, then mark it sent.
    try:
        email = await approve_and_send(message_id, body.draft, scope=scope_of(request))
    except SendRejectedError as exc:
        raise HTTPException(exc.status_code, exc.code) from exc
    except SendOutcomeUnknownError as exc:
        logger.warning("send outcome unknown for %s: %s", message_id, exc)
        raise HTTPException(status.HTTP_504_GATEWAY_TIMEOUT, "send_outcome_unknown") from exc
    except AccessExpiredSendError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "google_access_expired") from exc
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
async def system_info(request: Request) -> SystemInfo:
    settings = get_settings()
    scope = await scope_of_principal(principal_of(request))
    documents = await list_documents(scope) if scope else []
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
async def get_documents(request: Request) -> list[DocumentSummary]:
    # The knowledge base belongs to the mailbox it grounds replies for.
    scope = await scope_of_principal(principal_of(request))
    if scope is None:
        return []
    return await list_documents(scope)


@app.post("/documents", dependencies=[Depends(rate_limit_ingest), Depends(require_mailbox)])
async def add_document(request: DocumentRequest, http: Request) -> dict[str, int]:
    # Interim persist path: paste text -> chunk/embed/store.
    count = await ingest_text(f"paste://{request.title}", request.title, request.text,
                              scope=scope_of(http).owner_of_new_rows())
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


@app.post("/documents/upload", dependencies=[Depends(rate_limit_ingest), Depends(require_mailbox)])
async def upload_document(file: UploadFile, request: Request) -> dict[str, int]:
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
    count = await ingest_text(f"upload://{filename}", filename, text,
                              scope=scope_of(request).owner_of_new_rows())
    return {"chunks": count}
