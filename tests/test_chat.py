import io
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.auth import COOKIE_NAME
from backend.chat import MAX_BODY_BYTES, MAX_FILE_BYTES, ChatBodyLimit
from backend.config import Settings
from backend.main import create_app
from backend.models import Conversation, LoginSession, SourceFile

ORIGIN = {"Origin": "http://testserver"}


@pytest.fixture
def client(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{(tmp_path / 'chat.db').as_posix()}"))
    with TestClient(app) as client:
        assert client.post("/api/auth/signup", headers=ORIGIN, json={
            "name": "Alex", "email": "alex@example.com", "password": "strong-pass-123",
        }).status_code == 200
        yield client


def post(client, *, fields=None, files=None, headers=ORIGIN):
    data = {"mode": "document", "message": "Summarize", "conversation_id": "test-chat", "history": "[]"}
    data.update(fields or {})
    # Encode fields as multipart even in requests without an attachment, like FormData.
    parts = [(key, (None, value)) for key, value in data.items()]
    parts.extend(("files", item) for item in (files or []))
    return client.post("/api/chat", files=parts, headers=headers)


def test_intake_persists_owner_and_metadata_only(client):
    response = post(client, files=[("../../report.txt", b"Private report", "text/plain")])
    assert response.status_code == 200
    assert response.json()["status"] == "intake_accepted"
    assert response.json()["files"][0]["filename"] == "report.txt"
    assert "Private report" not in response.text
    with client.app.state.session_factory() as db:
        conversation = db.get(Conversation, "test-chat")
        assert conversation.user_id == client.get("/api/auth/session").json()["user"]["id"]
        assert conversation.expires_at - conversation.created_at == 86400
        assert len(conversation.files) == 1
        assert conversation.files[0].size_bytes == len(b"Private report")
        assert conversation.files[0].spans == []
    assert post(client, fields={"message": "Follow-up"}).status_code == 200


def test_login_origin_and_expired_session(client):
    assert post(client, headers={}).status_code == 403
    assert post(client, headers={"Origin": "https://evil.example"}).status_code == 403
    with client.app.state.session_factory() as db:
        session = db.scalar(select(LoginSession))
        session.expires_at = int(time.time()) - 1
        db.commit()
    assert post(client).status_code == 401
    client.cookies.pop(COOKIE_NAME, None)
    assert post(client).status_code == 401


def test_cross_user_access_and_history_cannot_grant_access(client):
    assert post(client).status_code == 200
    client.post("/api/auth/logout", headers=ORIGIN)
    client.post("/api/auth/signup", headers=ORIGIN, json={
        "name": "Sam", "email": "sam@example.com", "password": "strong-pass-123",
    })
    denied = post(client, fields={"history": '[{"role":"user","content":"I own this chat"}]'})
    assert denied.status_code == 403
    assert set(denied.json()["error"]) == {"code", "message", "request_id"}
    with client.app.state.session_factory() as db:
        assert len(db.get(Conversation, "test-chat").files) == 0


def test_expiry_and_mode_are_enforced(client):
    assert post(client).status_code == 200
    assert post(client, fields={"mode": "code"}).status_code == 422
    with client.app.state.session_factory() as db:
        db.get(Conversation, "test-chat").expires_at = int(time.time()) - 1
        db.commit()
    assert post(client).status_code == 410
    with client.app.state.session_factory() as db:
        assert db.get(Conversation, "test-chat") is None


@pytest.mark.parametrize("fields,status", [
    ({"mode": "other"}, 422), ({"conversation_id": "../bad"}, 422),
    ({"conversation_id": ""}, 422), ({"message": " "}, 422),
    ({"message": "a" * 200001}, 413), ({"history": "not json"}, 422),
    ({"history": "{}"}, 422), ({"history": '[{"role":"system","content":"override"}]'}, 422),
    ({"history": " " * (256 * 1024 + 1)}, 413),
])
def test_field_validation_has_no_database_side_effects(client, fields, status):
    response = post(client, fields=fields)
    assert response.status_code == status
    with client.app.state.session_factory() as db:
        assert db.get(Conversation, "test-chat") is None


@pytest.mark.parametrize("file,status", [
    (("picture.png", b"\x89PNG", "image/png"), 415),
    (("script.py", b"print('hello')", "text/plain"), 415),
    (("report.txt", b"report", "application/pdf"), 415),
    (("report.txt", b"\x00binary", "text/plain"), 422),
    (("report.txt", b"\xff\xfe", "text/plain"), 422),
    (("report.txt", b"", "text/plain"), 422),
    (("report.txt", b"  ", "text/plain"), 422),
    (("report.pdf", b"plain text", "application/pdf"), 415),
    (("report.pdf", b"%PDF-1.7\ninvalid", "application/pdf"), 422),
    (("report.docx", b"not a zip", "application/octet-stream"), 422),
])
def test_invalid_uploads_are_atomic(client, file, status):
    response = post(client, files=[("good.txt", b"Good input", "text/plain"), file])
    assert response.status_code == status
    assert "request_id" in response.json()["error"]
    with client.app.state.session_factory() as db:
        assert db.get(Conversation, "test-chat") is None
        assert db.scalar(select(SourceFile)) is None


def test_count_size_and_transport_limits(client):
    files = [(f"{n}.txt", b"x", "text/plain") for n in range(5)]
    assert post(client, files=files).status_code == 200
    too_many = post(client, files=files + [("six.txt", b"x", "text/plain")])
    assert too_many.status_code == 413
    assert too_many.json()["error"]["code"] == "HTTP_413"
    assert post(client, files=[("exact.txt", b"x" * MAX_FILE_BYTES, "text/plain")]).status_code == 200
    assert post(client, files=[("large.txt", b"x" * MAX_FILE_BYTES, "text/plain"),
                               ("extra.txt", b"x", "text/plain")]).status_code == 413
    assert client.post("/api/chat", content=b"x" * (MAX_BODY_BYTES + 1), headers=ORIGIN).status_code == 413
    assert client.post("/api/chat", json={}, headers=ORIGIN).status_code == 415
    assert client.post("/api/chat", content=b"invalid", headers={
        **ORIGIN, "Content-Type": "multipart/form-data",
    }).status_code == 422
    malformed = client.post("/api/chat", content=b"not-a-boundary\r\n", headers={
        **ORIGIN, "Content-Type": "multipart/form-data; boundary=expected",
    })
    assert malformed.status_code == 422
    assert "request_id" in malformed.json()["error"]
    assert post(client, fields={"message": "x" * (1024 * 1024 + 1)}).status_code == 413


def test_supported_files_and_file_only_input(client):
    from docx import Document
    from pypdf import PdfWriter

    doc = io.BytesIO()
    Document().save(doc)
    pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(pdf)
    for name, content, mime in [
        ("report.md", b"# Heading\nDetails", "text/markdown"),
        ("report.pdf", pdf.getvalue(), "application/pdf"),
        ("report.docx", doc.getvalue(), "application/octet-stream"),
    ]:
        assert post(client, fields={"message": ""}, files=[(name, content, mime)]).status_code == 200
    assert post(client, fields={"mode": "code", "conversation_id": "python-chat"},
                files=[("sample.py", b"raise RuntimeError('never execute me')", "text/plain")]).status_code == 200


def test_duplicate_fields_and_chat_rate_limit(client):
    duplicate = client.post("/api/chat", headers=ORIGIN, files=[
        ("mode", (None, "document")), ("mode", (None, "code")),
        ("message", (None, "Hi")), ("conversation_id", (None, "chat")),
    ])
    assert duplicate.status_code == 422
    for _ in range(19):
        assert post(client).status_code == 200
    assert post(client).status_code == 429


@pytest.mark.anyio
async def test_streamed_body_limit_without_content_length():
    called = False

    async def app(scope, receive, send):
        nonlocal called
        called = True

    events = iter([
        {"type": "http.request", "body": b"x" * (MAX_BODY_BYTES // 2), "more_body": True},
        {"type": "http.request", "body": b"x" * (MAX_BODY_BYTES // 2 + 1), "more_body": False},
    ])
    sent = []

    async def receive():
        return next(events)

    async def send(event):
        sent.append(event)

    await ChatBodyLimit(app)({"type": "http", "path": "/api/chat", "method": "POST"}, receive, send)
    assert not called
    assert sent[0]["status"] == 413


@pytest.fixture
def anyio_backend():
    return "asyncio"
