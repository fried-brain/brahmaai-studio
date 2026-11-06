from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.auth import router as auth_router
from app.api.assistant import router as assistant_router
from app.api.projects import router as projects_router
from app.core.config import Settings, get_settings
from app.core.database import Base, build_engine, build_session_factory
from app.models import User, UserSession  # noqa: F401 - registers model metadata
from app.services.local_llm import LocalLLMClient


def create_app(
    database_url: str | None = None,
    create_tables: bool = False,
    secure_cookies: bool | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_database_url = database_url or resolved_settings.database_url
    engine = build_engine(resolved_database_url) if resolved_database_url else None
    session_factory = build_session_factory(engine) if engine is not None else None
    local_llm_client = LocalLLMClient(resolved_settings)
    if create_tables and engine is not None:
        Base.metadata.create_all(bind=engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        local_llm_client.http.close()
        if engine is not None:
            engine.dispose()

    app = FastAPI(
        title="BrahmaAI Studio API",
        version="0.1.0",
        description="Foundation API for BrahmaAI Studio.",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.local_llm_client = local_llm_client
    app.state.secure_cookies = resolved_settings.secure_cookies if secure_cookies is None else secure_cookies
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.get("/api/v1/health", tags=["system"])
    def health() -> dict[str, str]:
        database_state = "not_configured"
        if engine is not None:
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                database_state = "connected"
            except SQLAlchemyError:
                raise HTTPException(status_code=503, detail="Database unavailable") from None
        return {"status": "ok", "service": "brahmaai-studio-api", "database": database_state}

    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(assistant_router, prefix="/api/v1")
    app.include_router(projects_router, prefix="/api/v1")
    return app


app = create_app()
