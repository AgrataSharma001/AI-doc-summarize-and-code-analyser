"""Local account and opaque server-session endpoints."""

from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Annotated
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models import LoginSession, User

router = APIRouter(prefix="/api/auth", tags=["authentication"])
COOKIE_NAME = "docode_session"
_password_hasher = PasswordHasher()
_email_pattern = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required")
        return value

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not _email_pattern.fullmatch(value):
            raise ValueError("Enter a valid email address")
        return value


class LoginInput(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RateLimiter:
    """Small per-process limiter suitable for this single-laptop deployment."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, maximum: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window_seconds:
                events.popleft()
            if len(events) >= maximum:
                raise HTTPException(status_code=429, detail="Too many attempts. Try again shortly.")
            events.append(now)


def database(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def require_same_origin(request: Request) -> None:
    """Reject browser cookie mutations without same-origin evidence."""
    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        raise HTTPException(status_code=403, detail="Origin required")
    parsed = urlsplit(source)
    if (parsed.scheme, parsed.netloc.lower()) != (
        request.url.scheme,
        request.url.netloc.lower(),
    ):
        raise HTTPException(status_code=403, detail="Origin mismatch")


def public_user(user: User) -> dict[str, str]:
    return {"id": user.id, "name": user.name, "email": user.email}


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def require_user(request: Request, session: Annotated[Session, Depends(database)]) -> User:
    token = request.cookies.get(COOKIE_NAME)
    record = session.get(LoginSession, _hash_token(token)) if token else None
    if record is not None and record.expires_at <= int(time.time()):
        session.delete(record)
        session.commit()
        record = None
    user = session.get(User, record.user_id) if record is not None else None
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    return user


def _set_session_cookie(response: Response, token: str, request: Request) -> None:
    settings = request.app.state.settings
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_lifetime_seconds,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path="/",
    )


def _start_session(user: User, session: Session, response: Response, request: Request) -> None:
    now = int(time.time())
    token = secrets.token_urlsafe(32)
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        session.execute(
            delete(LoginSession).where(LoginSession.token_hash == _hash_token(old_token))
        )
    session.add(
        LoginSession(
            token_hash=_hash_token(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + request.app.state.settings.session_lifetime_seconds,
        )
    )
    session.commit()
    _set_session_cookie(response, token, request)


@router.get("/session")
def current_session(request: Request, session: Annotated[Session, Depends(database)]) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {"user": None}
    record = session.get(LoginSession, _hash_token(token))
    if record is None:
        return {"user": None}
    if record.expires_at <= int(time.time()):
        session.delete(record)
        session.commit()
        return {"user": None}
    user = session.get(User, record.user_id)
    return {"user": public_user(user) if user is not None else None}


@router.post("/signup", dependencies=[Depends(require_same_origin)])
def signup(
    payload: SignupInput,
    response: Response,
    request: Request,
    session: Annotated[Session, Depends(database)],
) -> dict:
    host = request.client.host if request.client else "unknown"
    request.app.state.auth_rate_limiter.check(f"signup:{host}", maximum=5)
    now = int(time.time())
    user = User(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        password_hash=_password_hasher.hash(payload.password),
        created_at=now,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    _start_session(user, session, response, request)
    return {"user": public_user(user)}


@router.post("/login", dependencies=[Depends(require_same_origin)])
def login(
    payload: LoginInput,
    response: Response,
    request: Request,
    session: Annotated[Session, Depends(database)],
) -> dict:
    host = request.client.host if request.client else "unknown"
    request.app.state.auth_rate_limiter.check(f"login:{host}", maximum=10)
    email = payload.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    try:
        _password_hasher.verify(user.password_hash, payload.password)
    except VerificationError as exc:
        raise HTTPException(status_code=401, detail="Invalid email or password") from exc
    _start_session(user, session, response, request)
    return {"user": public_user(user)}


@router.post("/logout", status_code=204, dependencies=[Depends(require_same_origin)])
def logout(request: Request, session: Annotated[Session, Depends(database)]) -> Response:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session.execute(delete(LoginSession).where(LoginSession.token_hash == _hash_token(token)))
        session.commit()
    response = Response(status_code=204)
    response.delete_cookie(COOKIE_NAME, path="/", secure=request.app.state.settings.secure_cookies)
    return response
