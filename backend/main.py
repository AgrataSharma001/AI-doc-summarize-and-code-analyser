"""FastAPI entry point. Run with: uvicorn backend.main:app --reload"""

from contextlib import asynccontextmanager
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.auth import RateLimiter
from backend.auth import router as auth_router
from backend.config import PROJECT_ROOT, Settings
from backend.db import make_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        migration_config = Config(str(PROJECT_ROOT / "alembic.ini"))
        migration_config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
        command.upgrade(migration_config, "head")
        app.state.engine = engine
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Docode API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    app.state.auth_rate_limiter = RateLimiter()

    @app.exception_handler(HTTPException)
    async def api_http_error(request: Request, exc: HTTPException):
        if not request.url.path.startswith("/api/"):
            return await http_exception_handler(request, exc)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {
                "code": f"HTTP_{exc.status_code}",
                "message": str(exc.detail),
                "request_id": str(uuid4()),
            }},
        )

    @app.exception_handler(RequestValidationError)
    async def api_validation_error(request: Request, exc: RequestValidationError):
        if not request.url.path.startswith("/api/"):
            return await request_validation_exception_handler(request, exc)
        # FastAPI's default validation body may contain rejected input values,
        # including a submitted password. Keep the browser response generic.
        return JSONResponse(
            status_code=422,
            content={"error": {
                "code": "VALIDATION_ERROR",
                "message": "Check the submitted fields.",
                "request_id": str(uuid4()),
            }},
        )

    @app.get("/health", tags=["operations"])
    def health() -> dict[str, str]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok"}

    app.include_router(auth_router)

    # Register API routes before the catch-all static mount.
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
    return app


app = create_app()
