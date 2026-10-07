"""Authenticated multipart intake. Model answering is a later milestone."""

from __future__ import annotations

import io
import json
import re
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from typing import Annotated
from uuid import uuid4
from xml.etree import ElementTree

from fastapi import APIRouter, Depends, HTTPException, Request
from python_multipart.exceptions import MultipartParseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

from backend.auth import database, require_same_origin, require_user
from backend.models import Conversation, SourceFile, User

MAX_FILES = 5
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_BODY_BYTES = 12 * 1024 * 1024
MAX_MESSAGE_CHARS = 200_000
MAX_HISTORY_BYTES = 256 * 1024
RETENTION_SECONDS = 24 * 60 * 60
EXTENSIONS = {"document": {".txt", ".md", ".pdf", ".docx"}, "code": {".py"}}
MEDIA_TYPES = {
    ".txt": {"text/plain"},
    ".md": {"text/plain", "text/markdown", "text/x-markdown"},
    ".py": {"text/plain", "text/x-python", "text/x-python-script", "application/x-python-code"},
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
}
router = APIRouter(prefix="/api", tags=["chat"])


@asynccontextmanager
async def chat_form(request: Request):
    try:
        async with request.form(max_files=MAX_FILES, max_fields=4, max_part_size=1024 * 1024) as form:
            yield form
    except StarletteHTTPException as exc:
        if exc.status_code == 400:
            limit = any(part in str(exc.detail) for part in ("Too many files", "Too many fields", "Part exceeded"))
            raise HTTPException(413 if limit else 422, "Multipart limits exceeded." if limit else "Malformed multipart request.") from exc
        raise
    except MultipartParseError as exc:
        raise HTTPException(422, "Malformed multipart request.") from exc


class ChatBodyLimit:
    """Bound multipart buffering even when Content-Length is absent or dishonest."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/chat" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            chunk = event.get("body", b"")
            if len(body) + len(chunk) > MAX_BODY_BYTES:
                response = JSONResponse(status_code=413, content={"error": {
                    "code": "HTTP_413", "message": "Request exceeds the 12 MiB body limit.",
                    "request_id": str(uuid4()),
                }})
                return await response(scope, receive, send)
            body.extend(chunk)
            if not event.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def validate_file(filename: str, media_type: str, content: bytes, mode: str) -> str:
    # Filenames are display metadata only; never use them as filesystem paths.
    if not filename or len(filename) > 255 or any(ord(c) < 32 for c in filename):
        raise HTTPException(422, "Invalid filename.")
    name = PurePosixPath(filename.replace("\\", "/")).name
    extension = PurePosixPath(name).suffix.lower()
    if extension not in EXTENSIONS[mode]:
        raise HTTPException(415, f"Unsupported file type for {mode} mode.")
    mime = media_type.split(";", 1)[0].strip().lower()
    if mime and mime != "application/octet-stream" and mime not in MEDIA_TYPES[extension]:
        raise HTTPException(415, "File MIME type does not match its extension.")
    if not content:
        raise HTTPException(422, "Uploaded files must not be empty.")
    if extension in {".txt", ".md", ".py"}:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(422, "Text files must use UTF-8 encoding.") from exc
        if not text.strip() or any(ord(c) < 32 and c not in "\t\n\r\f" for c in text):
            raise HTTPException(422, "File must contain nonblank text, without binary data.")
        if content.startswith((b"%PDF-", b"PK\x03\x04", b"\x89PNG")):
            raise HTTPException(415, "File contents do not match a text file.")
    elif extension == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(415, "File contents do not match a PDF.")
        # Extraction and image-only detection belong to the document extraction phase.
        from pypdf import PdfReader

        try:
            pdf = PdfReader(io.BytesIO(content), strict=True)
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError("Encrypted or empty PDF")
        except Exception as exc:
            raise HTTPException(422, "PDF is corrupt, encrypted, or has no pages.") from exc
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                entries = archive.infolist()
                names = [entry.filename for entry in entries]
                if (len(entries) > 1000 or len(names) != len(set(names))
                        or sum(entry.file_size for entry in entries) > 20 * 1024 * 1024
                        or any(entry.flag_bits & 1 for entry in entries)):
                    raise ValueError("Unsafe archive")
                types = archive.read("[Content_Types].xml")
                document = archive.read("word/document.xml")
                if b"<!DOCTYPE" in types.upper() or b"<!DOCTYPE" in document.upper():
                    raise ValueError("Unsupported XML")
                root = ElementTree.fromstring(types)
                expected = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                if not any(e.attrib.get("PartName") == "/word/document.xml"
                           and e.attrib.get("ContentType") == expected for e in root):
                    raise ValueError("Not a DOCX document")
                if ElementTree.fromstring(document).tag != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document":
                    raise ValueError("Invalid document XML")
        except Exception as exc:
            raise HTTPException(422, "DOCX is corrupt or unsupported.") from exc
    return name


def validate_history(raw: str) -> None:
    if len(raw.encode("utf-8")) > MAX_HISTORY_BYTES:
        raise HTTPException(413, "History exceeds the 256 KiB limit.")
    try:
        history = json.loads(raw)
    except (ValueError, RecursionError) as exc:
        raise HTTPException(422, "History must be a JSON array.") from exc
    if not isinstance(history, list) or len(history) > 200:
        raise HTTPException(422, "History must contain at most 200 messages.")
    for entry in history:
        if (not isinstance(entry, dict) or entry.get("role") not in {"user", "assistant"}
                or not isinstance(entry.get("content"), str)
                or not isinstance(entry.get("attachments", []), list)):
            raise HTTPException(422, "Invalid history message.")
    # Deliberately discard browser history: it grants no access to stored context.


@router.post("/chat", dependencies=[Depends(require_same_origin)])
async def chat(
    request: Request,
    user: Annotated[User, Depends(require_user)],
    session: Annotated[Session, Depends(database)],
) -> dict:
    request.app.state.chat_rate_limiter.check(f"chat:{user.id}", maximum=20)
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(415, "Chat requires multipart/form-data.")
    async with chat_form(request) as form:
        allowed = {"mode", "message", "conversation_id", "history", "files"}
        if set(form) - allowed:
            raise HTTPException(422, "Unexpected chat field.")
        fields = {}
        for name in allowed - {"files"}:
            values = form.getlist(name)
            if len(values) > 1 or any(not isinstance(v, str) for v in values):
                raise HTTPException(422, "Chat fields must be single text values.")
            fields[name] = values[0] if values else ("[]" if name == "history" else "")
        mode, message, conversation_id = (fields[n] for n in ("mode", "message", "conversation_id"))
        if mode not in EXTENSIONS:
            raise HTTPException(422, "Mode must be document or code.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", conversation_id):
            raise HTTPException(422, "Conversation ID must be 1-64 letters, digits, underscores, or hyphens.")
        if len(message) > MAX_MESSAGE_CHARS:
            raise HTTPException(413, "Message exceeds 200,000 characters.")
        validate_history(fields["history"])
        files = form.getlist("files")
        if any(not isinstance(f, UploadFile) for f in files):
            raise HTTPException(422, "Files must be uploaded file parts.")
        if not message.strip() and not files:
            raise HTTPException(422, "Provide a message or at least one file.")
        now = int(time.time())
        conversation = session.get(Conversation, conversation_id)
        if conversation is not None:
            if conversation.user_id != user.id:
                raise HTTPException(403, "Conversation access denied.")
            if conversation.expires_at <= now:
                session.delete(conversation)
                session.commit()
                raise HTTPException(410, "Conversation expired. Start a new conversation and reattach content.")
            if conversation.mode != mode:
                raise HTTPException(422, "Conversation mode cannot change.")
        validated = []
        total = 0
        for upload in files:
            content = await upload.read(MAX_FILE_BYTES - total + 1)
            total += len(content)
            if total > MAX_FILE_BYTES:
                raise HTTPException(413, "Files exceed the combined 10 MiB limit.")
            name = validate_file(upload.filename or "", upload.content_type or "", content, mode)
            validated.append(SourceFile(
                id=str(uuid4()), conversation_id=conversation_id, filename=name,
                media_type=min(MEDIA_TYPES[PurePosixPath(name).suffix.lower()]),
                size_bytes=len(content), created_at=now,
            ))
        if conversation is None:
            conversation = Conversation(id=conversation_id, user_id=user.id, mode=mode,
                                        created_at=now, expires_at=now + RETENTION_SECONDS)
            session.add(conversation)
        conversation.files.extend(validated)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, "Conversation changed. Retry the request.") from exc
    return {
        "status": "intake_accepted", "conversation_id": conversation_id,
        "reply": "Input validated. AI answers are not available yet. Reattach your content when analysis is enabled.",
        "files": [{"id": f.id, "filename": f.filename, "size_bytes": f.size_bytes} for f in validated],
    }
