"""FastAPI entrypoint.

Serves the Lane B retrieval demo: search (POST /search), the knowledge-base inventory
(GET /documents), and two write paths - paste text (POST /documents) and PDF upload
(POST /documents/upload). These are DEMO endpoints, not the finalized REST contract;
that belongs in specs/context/api-contracts.md with Lane D.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    Depends,
    FastAPI,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi import Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app import agent_client
from app.account_routes import router as account_router
from app.admin.app import admin_app
from app.agent_contract import Tone
from app.audit import AuditAction, audit
from app.audit_routes import router as audit_router
from app.contracts import (
    EMAILS_PER_PAGE,
    MAX_EMAILS_PER_PAGE,
    DashboardEmail,
    EmailPage,
)
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
    EMBEDDING_MODEL,
    MAX_DRAFT_CHARS,
    MAX_INSTRUCTION_CHARS,
    MAX_PASTE_CHARS,
    MAX_QUERY_CHARS,
    MAX_UPLOAD_BYTES,
    PDF_MAGIC,
    UPLOAD_CHUNK_BYTES,
)
from app.core.cors import PathScopedCORS, origins_from
from app.core.cursor import decode_cursor
from app.core.errors import (
    DomainError,
    ErrorCode,
    error_response,
    register_error_handlers,
)
from app.core.health import database_answers, health_router
from app.core.logging_setup import configure_logging
from app.core.middleware import request_context
from app.core.providers import Provider
from app.core.ratelimit import (
    rate_limit_detail,
    rate_limit_generation,
    rate_limit_ingest,
    rate_limit_list,
    rate_limit_send,
)
from app.core.typed_text import mask_typed_text
from app.dashboard import (
    approve_and_send,
    confirm_sender,
    email_detail,
    email_for_thread,
    list_dashboard_emails,
    refine_email,
    regenerate_email,
    translate_email,
)
from app.egress_log import save_egress
from app.gmail_send import SendError, SendOutcomeUnknownError
from app.holding_reply_routes import router as holding_reply_router
from app.private_mode import provider_for
from app.private_mode_routes import router as private_mode_router
from app.rag.chunk import extract_pdf_bytes
from app.rag.embedding_models import REGISTRY, check_columns
from app.rag.errors import EmbeddingError
from app.rag.generate import answer
from app.rag.ingest import ingest_text
from app.rag.library import DocumentSummary, delete_document, list_documents
from app.rag.mask import DocumentMaskingError
from app.rag.retrieve import ContextChunk, retrieve
from app.sign_in import router as sign_in_router
from app.writing_style_routes import router as writing_style_router
from model_gateway import track_egress
from model_runtime import ModelError

configure_logging()

@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """The API runs no background jobs: they live in the worker (app/worker.py)."""
    await check_columns()
    await mailbox.resolve_owner()
    yield
    await agent_client.close()


app = FastAPI(title="AImail backend", dependencies=[Depends(require_auth)], lifespan=_lifespan)
app.middleware("http")(request_context)
# Its own app, so the shared token never applies there: admin is a Supabase session (ADR 0004).
app.mount(ADMIN_PREFIX, admin_app)
app.include_router(health_router({"database": database_answers}))
app.include_router(sign_in_router)
app.include_router(account_router)
app.include_router(holding_reply_router)
app.include_router(private_mode_router)
app.include_router(writing_style_router)
app.include_router(audit_router)

# Dev CORS so the dashboard can call this API cross-origin. The regex covers any
# localhost/127.0.0.1 port (they are distinct origins to the browser); FRONTEND_ORIGINS lists
# the deployed dashboard origins. Admin paths get their own, credentialed
# policy for ADMIN_ORIGINS only (app/core/cors.py, ADR 0004).
app.add_middleware(
    PathScopedCORS,
    admin_prefix=ADMIN_PREFIX,
    admin_origins=origins_from(get_settings().admin_origins),
    public_origins=origins_from(get_settings().frontend_origins),
    public_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
)

_STATIC = Path(__file__).parent / "static"

logger = logging.getLogger(__name__)



register_error_handlers(app)


async def _ai_service_unreachable(request: Request, exc: Exception) -> JSONResponse:
    # Embedding and generation failures become a clean 503 instead of a raw 500.
    logger.warning("AI service unreachable on %s: %s", request.url.path, exc)
    return error_response(ErrorCode.AI_SERVICE_UNREACHABLE)


for _ai_exc in (EmbeddingError, ModelError):
    app.add_exception_handler(_ai_exc, _ai_service_unreachable)


@app.exception_handler(DocumentMaskingError)
async def _masking_unavailable(request: Request, exc: DocumentMaskingError) -> JSONResponse:
    # Refused, not stored unmasked: the same fail-closed rule the listener follows for email.
    logger.warning("document masking unavailable: %s", exc)
    return error_response(ErrorCode.MASKING_UNAVAILABLE)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    k: int = Field(default=5, ge=1, le=20)


class DocumentRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    # Capped for the same reason as the upload path: this is the other unbounded ingestion input.
    text: str = Field(min_length=1, max_length=MAX_PASTE_CHARS)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)
    k: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    answer: str
    sources: list[ContextChunk]


@app.get("/")
async def demo_page() -> FileResponse:
    return FileResponse(_STATIC / "demo.html")


@app.post("/search", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def search(request: SearchRequest, http: Request) -> list[ContextChunk]:
    # A typed query is embedded, so fixed-format details are masked first; by the user's own provider.
    scope = scope_of(http)
    provider = await provider_for(scope.owner_id)
    with track_egress() as sent:
        found = await retrieve(mask_typed_text(request.query), request.k, scope=scope, provider=provider)
    await save_egress(sent, user_id=scope.owner_id, message_id=None)
    return found


@app.post("/ask", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def ask(request: AskRequest, http: Request) -> AskResponse:
    # Full RAG loop demo: retrieve policy chunks, then generate a grounded answer from them.
    question = mask_typed_text(request.question)
    scope = scope_of(http)
    provider = await provider_for(scope.owner_id)
    with track_egress() as sent:
        chunks = await retrieve(question, request.k, scope=scope, provider=provider)
        text = await answer(question, chunks, provider=provider)
    await save_egress(sent, user_id=scope.owner_id, message_id=None)
    return AskResponse(answer=text, sources=chunks)


@app.get("/emails", dependencies=[Depends(rate_limit_list)])
async def emails(request: Request, cursor: str | None = None,
                 limit: int = Query(EMAILS_PER_PAGE, ge=1, le=MAX_EMAILS_PER_PAGE)) -> EmailPage:
    # Fast list: Han's Email shape from ingested messages + Lane B priority (no generation).
    # Someone with no connected mailbox sees an empty inbox, not an error.
    principal = principal_of(request)
    scope = await scope_of_principal(principal)
    if scope is None:
        return EmailPage(emails=[])
    after = decode_cursor(cursor) if cursor else None
    return await list_dashboard_emails(scope, principal.email or mailbox.owner(), limit, after)


@app.get("/emails/{message_id}", dependencies=[Depends(rate_limit_detail), Depends(require_mailbox)])
async def email_detail_route(message_id: str, request: Request) -> DashboardEmail:
    # Detail view: adds Lane C generation (retrieve + /process-email) for one opened email.
    email = await email_detail(message_id, scope=scope_of(request))
    return _found(email)


# Gmail thread ids are 16 hex digits; bounded so the path never carries anything else.
GMAIL_THREAD_ID = r"^[0-9a-f]{8,24}$"


@app.get("/emails/by-thread/{thread_id}", dependencies=[Depends(rate_limit_detail), Depends(require_mailbox)])
async def email_for_thread_route(
    thread_id: Annotated[str, PathParam(pattern=GMAIL_THREAD_ID)], request: Request
) -> DashboardEmail:
    # The Chrome extension's lookup: the email Gmail has open, by its thread.
    email = await email_for_thread(thread_id, scope=scope_of(request))
    return _found(email)


def _found[T](value: T | None) -> T:
    """Someone else's email answers exactly like a missing one, so an id reveals nothing."""
    if value is None:
        raise DomainError(ErrorCode.NOT_FOUND)
    return value


class RegenerateRequest(BaseModel):
    tone: Tone = Tone.PROFESSIONAL


@app.post("/emails/{message_id}/confirm-sender", dependencies=[Depends(require_mailbox)])
async def confirm_sender_route(message_id: str, request: Request) -> DashboardEmail:
    # The owner checked a sender that failed SPF/DKIM/DMARC and says it is real; drafting resumes.
    email = await confirm_sender(message_id, scope=scope_of(request))
    return _found(email)


@app.post("/emails/{message_id}/regenerate", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def regenerate_email_route(
    message_id: str, request: Request, body: RegenerateRequest | None = None
) -> DashboardEmail:
    # Force a fresh draft in the requested tone (Regenerate button / tone toggle). Body optional.
    return _found(await regenerate_email(message_id, scope=scope_of(request),
                                         tone=body.tone if body else Tone.PROFESSIONAL))


class RefineRequest(BaseModel):
    instruction: str = Field(max_length=MAX_INSTRUCTION_CHARS)  # e.g. "make it shorter", "add a deadline"
    draft: str = Field(max_length=MAX_DRAFT_CHARS)  # the current draft to revise
    # The tone the reader has chosen, so the revision and its review keep it.
    tone: Tone = Tone.PROFESSIONAL


@app.post("/emails/{message_id}/refine", dependencies=[Depends(rate_limit_generation), Depends(require_mailbox)])
async def refine_email_route(message_id: str, body: RefineRequest, request: Request) -> DashboardEmail:
    # Revise the current draft per the user's instruction (dashboard's Refine box).
    return _found(await refine_email(message_id, body.instruction, body.draft, scope=scope_of(request),
                                     tone=body.tone))


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
    return TranslateResponse(**_found(await translate_email(message_id, body.language, scope=scope_of(request))))


class SendRequest(BaseModel):
    draft: str = Field(min_length=1, max_length=MAX_DRAFT_CHARS)  # the approved, possibly edited draft


@app.post("/emails/{message_id}/send", dependencies=[Depends(rate_limit_send), Depends(require_mailbox)])
async def send_email_route(message_id: str, body: SendRequest, request: Request) -> DashboardEmail:
    # Human-approved send: reply to the original sender with the draft, then mark it sent.
    try:
        email = await approve_and_send(message_id, body.draft, scope=scope_of(request))
    except (SendError, SendOutcomeUnknownError) as exc:
        # The reason stays in the log (it can name local credential paths); the answer carries the code.
        logger.warning("send failed for %s: %s", message_id, exc)
        raise
    return _found(email)


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
        embedding_model=EMBEDDING_MODEL,
        embedding_dim=REGISTRY[Provider.GEMINI].dimensions,
        priority_model=settings.priority_model,
        auth_enabled=bool(settings.backend_api_token),
        auto_generate=settings.auto_generate,
        generate_poll_seconds=settings.generate_poll_seconds,
        document_count=len(documents),
        chunk_count=sum(d["chunk_count"] for d in documents),
    )


@app.get("/documents", dependencies=[Depends(rate_limit_list)])
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


@app.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT,
            dependencies=[Depends(require_mailbox)])
async def remove_document(document_id: UUID, http: Request) -> Response:
    """Chunks and both kinds of vector go with it (ON DELETE CASCADE)."""
    if not await delete_document(document_id, scope_of(http)):
        raise DomainError(ErrorCode.NOT_FOUND)
    await audit(AuditAction.DOCUMENT_DELETED, user_id=scope_of(http).owner_id, document=document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _read_capped(file: UploadFile) -> bytes:
    """Stream the upload, aborting past MAX_UPLOAD_BYTES so a huge file is never buffered whole."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(UPLOAD_CHUNK_BYTES):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise DomainError(ErrorCode.TOO_LARGE, f"file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/documents/upload", dependencies=[Depends(rate_limit_ingest), Depends(require_mailbox)])
async def upload_document(file: UploadFile, request: Request) -> dict[str, int]:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise DomainError(ErrorCode.NOT_PDF, "only .pdf files are supported")
    data = await _read_capped(file)
    if not data.startswith(PDF_MAGIC):
        raise DomainError(ErrorCode.NOT_PDF, "the .pdf extension does not match the contents")
    try:
        # CPU-bound: off the event loop, so one large PDF does not stall every other request.
        text = await asyncio.to_thread(extract_pdf_bytes, data)
    except Exception as exc:
        raise DomainError(ErrorCode.UNREADABLE_PDF) from exc
    count = await ingest_text(f"upload://{filename}", filename, text,
                              scope=scope_of(request).owner_of_new_rows())
    return {"chunks": count}
