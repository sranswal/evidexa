"""Main FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from document_intelligence.api.csrf import verify_csrf_request
from document_intelligence.api.error_handlers import (
    authentication_handler,
    conflict_handler,
    entity_not_found_handler,
    forbidden_handler,
    rate_limit_handler,
    request_validation_handler,
    security_handler,
    storage_handler,
    unhandled_exception_handler,
    validation_handler,
)
from document_intelligence.api.routes import api_v1_router, health_router
from document_intelligence.core.config import settings
from document_intelligence.core.exceptions import (
    AuthenticationException,
    ConflictException,
    EntityNotFoundException,
    ForbiddenException,
    RateLimitException,
    SecurityException,
    StorageException,
    ValidationException,
)
from document_intelligence.core.logging import get_logger, setup_logging
from document_intelligence.infrastructure.persistence.database import engine
from document_intelligence.infrastructure.persistence.models import Base

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifespan coordinator."""
    # 1. Initialize logging and storage directories
    setup_logging(settings.log_level)
    settings.ensure_directories()

    # 2. Ensure schema tables are initialized
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully.")

    # 3. Recover any stale RUNNING processing runs from prior server terminations
    try:
        from document_intelligence.api.dependencies import (
            get_audit_service,
            get_forensic_processing_service,
            get_storage,
        )
        from document_intelligence.infrastructure.persistence.database import SessionLocal

        with SessionLocal() as db:
            audit = get_audit_service(db=db)
            storage = get_storage(app_settings=settings)
            service = get_forensic_processing_service(db=db, storage=storage, audit_service=audit)
            recovered = service.recover_stale_runs()
            if recovered > 0:
                logger.warning(
                    "Recovered %d stale processing run(s) left in RUNNING state.", recovered
                )
    except Exception as exc:
        logger.error("Failed to recover stale processing runs during startup: %s", exc)

    logger.info(
        "Application '%s' (v%s) started in '%s' environment.",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    yield
    logger.info("Application shutting down.")


def create_app() -> FastAPI:
    """Build and configure FastAPI application."""
    app = FastAPI(
        title="EVIDEXA API",
        version=settings.app_version,
        description="EVIDEXA - Intelligent document forensics and evidence analysis, powered by AI. Official API.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
    )

    # CSRF Protection Middleware for ambient cookie authentication
    @app.middleware("http")
    async def csrf_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        csrf_error = verify_csrf_request(request)
        if csrf_error:
            return csrf_error
        return await call_next(request)

    # Register Exception Handlers
    app.add_exception_handler(AuthenticationException, authentication_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ForbiddenException, forbidden_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitException, rate_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(EntityNotFoundException, entity_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ConflictException, conflict_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationException, validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SecurityException, security_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StorageException, storage_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, request_validation_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # Mount Routes
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


app = create_app()
