"""SQLite engine construction shared by the API and future migrations."""

from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        # The default database lives under ./data. SQLAlchemy does not create
        # parent directories for file-backed SQLite databases.
        db_file = Path(unquote(database_url.removeprefix("sqlite:///")))
        db_file.parent.mkdir(parents=True, exist_ok=True)

    options: dict = {}
    if database_url.startswith("sqlite:"):
        options["connect_args"] = {"check_same_thread": False}
        if database_url == "sqlite:///:memory:":
            options["poolclass"] = StaticPool

    return create_engine(database_url, pool_pre_ping=True, **options)

