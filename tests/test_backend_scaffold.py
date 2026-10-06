from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import PROJECT_ROOT, Settings
from backend.main import create_app


def test_local_api_and_frontend_share_origin(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            frontend_dir=PROJECT_ROOT / "Frontend",
        )
    )
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/api/auth/session").json() == {"user": None}
        page = client.get("/index.html")
        assert page.status_code == 200
        assert "Document workspace" in page.text

