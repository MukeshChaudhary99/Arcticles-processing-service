import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Direct script execution puts app/ on sys.path; package imports need its parent.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from asyncpg import PostgresError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, TimeoutError

from app.controllers.articles import router as article_router
from app.core.errors import ServiceError
from app.core.logging import (
    RequestContextMiddleware,
    configure_logging,
    request_id_context,
)
from app.core.settings import Settings, get_settings
from app.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging(settings.log_level)
        app.state.database = Database(settings)
        try:
            yield
        finally:
            await app.state.database.close()

    app = FastAPI(title="Tenant Article Service", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)
    app.include_router(article_router)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse(
            {"detail": exc.detail, "request_id": request_id_context.get()},
            status_code=exc.status_code,
        )

    @app.exception_handler(TimeoutError)
    async def pool_timeout(request: Request, exc: TimeoutError):
        return JSONResponse(
            {"detail": "Database is busy; retry later"}, status_code=503
        )

    @app.get("/health/live", tags=["health"])
    async def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def ready(request: Request):
        try:
            async with request.app.state.database.sessions() as session:
                await session.execute(text("SELECT 1"))
        except (SQLAlchemyError, PostgresError, OSError):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
