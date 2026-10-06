import hashlib
import time
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.auth import COOKIE_NAME
from backend.config import PROJECT_ROOT, Settings
from backend.main import create_app
from backend.models import LoginSession, User

ORIGIN = {"Origin": "http://testserver"}


def make_test_app(tmp_path: Path):
    return create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
            frontend_dir=PROJECT_ROOT / "Frontend",
        )
    )


def test_signup_session_logout_and_login(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={"name": "  Alex  ", "email": "ALEX@example.com", "password": "strong-pass-123"},
            headers=ORIGIN,
        )
        assert signup.status_code == 200
        user = signup.json()["user"]
        assert user["name"] == "Alex"
        assert user["email"] == "alex@example.com"
        assert set(user) == {"id", "name", "email"}
        cookie = signup.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        raw_token = client.cookies[COOKIE_NAME]

        with app.state.session_factory() as db:
            stored_user = db.scalar(select(User).where(User.email == "alex@example.com"))
            assert stored_user is not None
            assert stored_user.password_hash != "strong-pass-123"
            assert stored_user.password_hash.startswith("$argon2id$")
            stored_session = db.get(LoginSession, hashlib.sha256(raw_token.encode()).hexdigest())
            assert stored_session is not None
            assert stored_session.token_hash != raw_token

        assert client.get("/api/auth/session").json() == {"user": user}
        assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 204
        assert client.get("/api/auth/session").json() == {"user": None}

        failed = client.post(
            "/api/auth/login",
            json={"email": "alex@example.com", "password": "wrong"},
            headers=ORIGIN,
        )
        assert failed.status_code == 401
        assert failed.json()["error"]["code"] == "HTTP_401"
        login = client.post(
            "/api/auth/login",
            json={"email": "ALEX@example.com", "password": "strong-pass-123"},
            headers=ORIGIN,
        )
        assert login.status_code == 200
        assert login.json() == {"user": user}


def test_duplicate_email_and_origin_checks(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    payload = {"name": "Alex", "email": "alex@example.com", "password": "strong-pass-123"}
    with TestClient(app) as client:
        assert client.post("/api/auth/signup", json=payload).status_code == 403
        assert client.post(
            "/api/auth/signup", json=payload, headers={"Origin": "https://evil.example"}
        ).status_code == 403
        assert client.post("/api/auth/signup", json=payload, headers=ORIGIN).status_code == 200
        assert client.post("/api/auth/signup", json=payload, headers=ORIGIN).status_code == 409
        assert client.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
        assert client.get("/api/auth/session").json()["user"]["email"] == "alex@example.com"


def test_expired_session_is_rejected_and_deleted(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    with TestClient(app) as client:
        client.post(
            "/api/auth/signup",
            json={"name": "Alex", "email": "alex@example.com", "password": "strong-pass-123"},
            headers=ORIGIN,
        )
        raw_token = client.cookies[COOKIE_NAME]
        digest = hashlib.sha256(raw_token.encode()).hexdigest()
        with app.state.session_factory() as db:
            record = db.get(LoginSession, digest)
            assert record is not None
            record.expires_at = int(time.time()) - 1
            db.commit()
        assert client.get("/api/auth/session").json() == {"user": None}
        with app.state.session_factory() as db:
            assert db.get(LoginSession, digest) is None


def test_validation_does_not_echo_password_and_login_is_rate_limited(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    with TestClient(app) as client:
        invalid = client.post(
            "/api/auth/signup",
            json={"name": "Alex", "email": "alex@example.com", "password": "short"},
            headers=ORIGIN,
        )
        assert invalid.status_code == 422
        assert "short" not in invalid.text
        for _ in range(10):
            response = client.post(
                "/api/auth/login",
                json={"email": "missing@example.com", "password": "wrong"},
                headers=ORIGIN,
            )
            assert response.status_code == 401
        limited = client.post(
            "/api/auth/login",
            json={"email": "missing@example.com", "password": "wrong"},
            headers=ORIGIN,
        )
        assert limited.status_code == 429


def test_account_survives_app_restart(tmp_path: Path) -> None:
    payload = {"name": "Alex", "email": "alex@example.com", "password": "strong-pass-123"}
    with TestClient(make_test_app(tmp_path)) as client:
        assert client.post("/api/auth/signup", json=payload, headers=ORIGIN).status_code == 200

    with TestClient(make_test_app(tmp_path)) as client:
        login = client.post(
            "/api/auth/login",
            json={"email": payload["email"], "password": payload["password"]},
            headers=ORIGIN,
        )
        assert login.status_code == 200
        assert client.get("/api/auth/session").json() == login.json()
