"""FastAPI entry point. Run with: uvicorn backend.main:app --reload"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from backend.config import Settings
from backend.db import make_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Docode API", version="0.1.0", lifespan=lifespan)

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    @app.get("/api/auth/session", tags=["authentication"])
    def current_session() -> dict[str, None]:
        # P1-01 only establishes the frontend contract. Real sessions are the
        # next auth task; a guest response makes the current state explicit.
        return {"user": None}

    # Register API routes before the catch-all static mount.
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()

