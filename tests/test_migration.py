from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient

from backend.config import PROJECT_ROOT, Settings
from backend.main import create_app
from backend.models import Base


def test_initial_migration_matches_models(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'migration.db').as_posix()}",
            frontend_dir=PROJECT_ROOT / "Frontend",
        )
    )
    with TestClient(app), app.state.engine.connect() as connection:
        context = MigrationContext.configure(connection)
        assert compare_metadata(context, Base.metadata) == []
