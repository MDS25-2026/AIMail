"""Each user sees and acts on only their own mail and documents (per-user mailboxes, step 3).

A user with a connected Gmail is scoped to rows carrying their user id. Rows with no owner belong
to the original single mailbox's owner until that account connects. Anyone else's id reads as
missing (404), never as forbidden, so an id reveals nothing about what exists.
"""

import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql

from app import dashboard, sign_in
from app.contracts import EmailPage
from app.core import ownership, supabase_auth
from app.core.auth import SESSION_COOKIE
from app.core.config import get_settings
from app.core.ownership import EVERYTHING, LEGACY, Scope
from app.core.providers import Provider
from app.db.models import Message
from app.main import app
from app.rag import ingest, library, retrieve
from tests.conftest import AUTH_HEADERS

SUPABASE = "https://project.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
ALICE = UUID("aaaaaaaa-0000-4000-8000-000000000001")
BOB = UUID("bbbbbbbb-0000-4000-8000-000000000002")
LEGACY_OWNER = "owner@gmail.com"


@dataclass(frozen=True)
class _SigningKey:
    key: object


class _FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return _SigningKey(KEY.public_key())


def _token(user_id: UUID | str, email: str) -> str:
    claims = {"sub": str(user_id), "email": email, "aud": "authenticated",
              "iss": f"{SUPABASE}/auth/v1", "exp": int(time.time()) + 600}
    return jwt.encode(claims, KEY, algorithm="ES256")


async def _never(_user_id):
    return False


@pytest.fixture
def seen(monkeypatch, test_settings):
    """Signs users in, connects only Alice, and records the scope every dashboard call receives."""
    for name, value in (("SUPABASE_URL", SUPABASE), ("SUPABASE_ANON_KEY", "anon"),
                        ("MAILBOX_OWNER_EMAIL", LEGACY_OWNER)):
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    monkeypatch.setattr(supabase_auth, "_jwks", lambda base: _FakeJwks())

    async def connected(user_id):
        return user_id == ALICE

    monkeypatch.setattr(ownership, "is_connected", connected)
    monkeypatch.setattr(sign_in.connections, "needs_reconnect", _never)
    scopes: list[Scope] = []

    async def record(*_args, scope, **_kwargs):
        scopes.append(scope)

    async def listed(scope, policy_email, limit, after):
        scopes.append(scope)
        return EmailPage(emails=[])

    for name in ("email_detail", "regenerate_email", "refine_email", "translate_email", "approve_and_send"):
        monkeypatch.setattr(f"app.main.{name}", record)
    monkeypatch.setattr("app.main.list_dashboard_emails", listed)
    return scopes


def _as(user_id: UUID | str, email: str) -> TestClient:
    client = TestClient(app)
    client.cookies.set(SESSION_COOKIE, _token(user_id, email))
    client.headers["X-AIMail-Client"] = "1"
    return client


ACTIONS = (
    ("get", "/emails/m1", None),
    ("post", "/emails/m1/regenerate", {}),
    ("post", "/emails/m1/refine", {"instruction": "shorter", "draft": "Hi"}),
    ("post", "/emails/m1/translate", {"language": "ms"}),
    ("post", "/emails/m1/send", {"draft": "Thanks"}),
)


@pytest.mark.parametrize(("method", "path", "body"), ACTIONS)
def test_every_email_action_runs_in_the_signed_in_users_own_scope(seen, method, path, body):
    getattr(_as(ALICE, "alice@gmail.com"), method)(path, **({"json": body} if body is not None else {}))
    assert seen == [Scope(owner_id=ALICE)]


@pytest.mark.parametrize(("method", "path", "body"), ACTIONS)
def test_a_user_with_no_connected_mailbox_gets_404_and_nothing_runs(seen, method, path, body):
    response = getattr(_as(BOB, "bob@gmail.com"), method)(path, **({"json": body} if body is not None else {}))
    assert response.status_code == 404
    assert seen == []


def test_the_inbox_lists_only_the_users_own_mail(seen):
    _as(ALICE, "alice@gmail.com").get("/emails")
    assert seen == [Scope(owner_id=ALICE)]
    assert _as(BOB, "bob@gmail.com").get("/emails").json()["emails"] == []


def test_the_original_mailbox_owner_keeps_the_unowned_rows_until_they_connect(seen):
    _as("not-a-uuid-in-old-tokens", LEGACY_OWNER).get("/emails")
    assert seen == [LEGACY]


def test_scripts_with_the_shared_token_still_see_everything(seen):
    TestClient(app).get("/emails", headers=AUTH_HEADERS)
    assert seen == [EVERYTHING]


def test_the_session_says_connected_only_for_a_connected_user(seen):
    assert _as(ALICE, "alice@gmail.com").get("/auth/session").json()["hasMailbox"] is True
    assert _as(BOB, "bob@gmail.com").get("/auth/session").json()["hasMailbox"] is False


# ---------- The filter each scope puts on the query ----------

def _sql(clause) -> str:
    return str(clause.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_a_users_scope_matches_only_their_own_rows():
    assert _sql(Scope(owner_id=ALICE).where(Message.user_id)) == f"messages.user_id = '{ALICE}'"


def test_the_legacy_scope_matches_only_unowned_rows():
    assert _sql(LEGACY.where(Message.user_id)) == "messages.user_id IS NULL"


def test_a_script_writing_a_document_files_it_under_the_original_mailbox():
    assert EVERYTHING.owner_of_new_rows() == LEGACY
    assert Scope(owner_id=ALICE).owner_of_new_rows() == Scope(owner_id=ALICE)


class _Capture:
    """A session stand-in that records the statement instead of running it."""

    def __init__(self):
        self.statements = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_exc):
        return False

    async def scalar(self, statement):
        self.statements.append(statement)

    async def scalars(self, statement):
        self.statements.append(statement)
        return _Rows()

    async def execute(self, statement):
        self.statements.append(statement)
        return _Rows()


class _Rows:
    def all(self):
        return []

    def scalars(self):
        return self

    def first(self):
        return None


@pytest.fixture
def captured(monkeypatch):
    session = _Capture()
    for module in (dashboard, library, retrieve):
        monkeypatch.setattr(module, "get_sessionmaker", lambda: lambda: session)
    return session.statements


def test_loading_an_email_by_id_is_filtered_by_owner(captured):
    asyncio.run(dashboard._load(ALICE, Scope(owner_id=BOB)))
    assert f"messages.user_id = '{BOB}'" in _sql(captured[0])


def test_the_inbox_query_is_filtered_by_owner(captured):
    asyncio.run(dashboard.list_dashboard_emails(Scope(owner_id=ALICE), "alice@gmail.com", 50, None))
    assert f"messages.user_id = '{ALICE}'" in _sql(captured[0])


def test_a_thread_only_includes_the_same_owners_messages():
    session = _Capture()
    asyncio.run(dashboard._thread_of(session, Message(id=ALICE, thread_id="t1", user_id=BOB)))
    assert f"messages.user_id = '{BOB}'" in _sql(session.statements[0])


def test_the_document_list_is_filtered_by_owner(captured):
    asyncio.run(library.list_documents(Scope(owner_id=ALICE)))
    assert f"document.user_id = '{ALICE}'" in _sql(captured[0])


def test_retrieval_only_grounds_on_the_owners_documents(captured, monkeypatch):
    async def vector(_text, **_kwargs):
        return [0.0] * 3

    monkeypatch.setattr(retrieve.model_gateway, "embed_query", vector)
    asyncio.run(retrieve.retrieve("leave policy", 5, scope=Scope(owner_id=ALICE), provider=Provider.GEMINI))
    assert f"document.user_id = '{ALICE}'" in _sql(captured[0])


def test_re_uploading_replaces_only_the_uploaders_own_copy_and_files_it_under_them():
    session = _Capture()
    session.added = []
    session.add = session.added.append

    async def flush():
        return None

    session.flush = flush
    asyncio.run(ingest._replace_document(session, Scope(owner_id=ALICE), "upload://a.pdf", "a", "policy"))
    assert f"document.user_id = '{ALICE}'" in _sql(session.statements[0])
    assert session.added[0].user_id == ALICE


# ---------- The Chrome extension's lookup by Gmail thread ----------

def test_the_extension_looks_up_the_open_thread_in_the_users_own_scope(seen, monkeypatch):
    calls = []

    async def by_thread(thread_id, *, scope):
        calls.append((thread_id, scope))

    monkeypatch.setattr("app.main.email_for_thread", by_thread)
    assert _as(ALICE, "alice@gmail.com").get("/emails/by-thread/1a10b0c2d3e4f5a6").status_code == 404
    assert calls == [("1a10b0c2d3e4f5a6", Scope(owner_id=ALICE))]


def test_a_user_with_no_mailbox_never_reaches_the_thread_lookup(seen, monkeypatch):
    async def by_thread(*_args, **_kwargs):
        raise AssertionError("looked up a thread for someone with no mailbox")

    monkeypatch.setattr("app.main.email_for_thread", by_thread)
    assert _as(BOB, "bob@gmail.com").get("/emails/by-thread/1a10b0c2d3e4f5a6").status_code == 404


def test_anything_but_a_gmail_thread_id_is_refused_before_any_lookup(seen):
    response = TestClient(app).get("/emails/by-thread/not-an-id%27%3B", headers=AUTH_HEADERS)
    assert response.status_code == 422


def test_the_thread_lookup_takes_the_newest_message_the_caller_owns(captured):
    asyncio.run(dashboard.email_for_thread("1a10b0c2d3e4f5a6", scope=Scope(owner_id=ALICE)))
    sql = _sql(captured[0])
    assert "messages.thread_id = '1a10b0c2d3e4f5a6'" in sql
    assert f"messages.user_id = '{ALICE}'" in sql
    assert "ORDER BY messages.received_at DESC NULLS LAST" in sql
