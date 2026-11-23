"""Main FastAPI application entrypoint."""

import asyncio
import shutil
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

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


async def _cleanup_ephemeral_sandbox_cases() -> None:
    """Periodically purges non-seeded user uploads older than 1 hour to maintain an ephemeral privacy sandbox."""
    while True:
        try:
            await asyncio.sleep(1800)  # Check every 30 minutes
            from datetime import timedelta
            from document_intelligence.domain.identifiers import utc_now
            from document_intelligence.infrastructure.persistence.database import SessionLocal
            from document_intelligence.infrastructure.persistence.models import CaseModel

            cutoff = utc_now() - timedelta(hours=1)
            with SessionLocal() as db:
                expired_cases = (
                    db.query(CaseModel)
                    .filter(
                        CaseModel.id.notin_(["case-demo-0881", "case-demo-0942"]),
                        CaseModel.created_at < cutoff,
                    )
                    .all()
                )
                for case in expired_cases:
                    case_orig = Path(settings.data_dir) / "originals" / case.id
                    if case_orig.exists():
                        shutil.rmtree(case_orig, ignore_errors=True)
                    case_art = Path(settings.data_dir) / "artifacts" / case.id
                    if case_art.exists():
                        shutil.rmtree(case_art, ignore_errors=True)
                    db.delete(case)
                if expired_cases:
                    db.commit()
                    logger.info("Purged %d expired ephemeral sandbox case(s).", len(expired_cases))
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning("Ephemeral cleanup notice: %s", exc)


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

    # 4. Idempotently ensure initial demo data and examiner account exist (for zero-shell cloud deployments like Render)
    try:
        from document_intelligence.infrastructure.persistence.database import SessionLocal
        from document_intelligence.infrastructure.persistence.models import UserModel

        with SessionLocal() as db:
            examiner = db.query(UserModel).filter(UserModel.username == "examiner").first()
            if not examiner:
                logger.info("Initializing baseline demo dataset and examiner account on startup...")
                from scripts.seed_demo_investigation import seed_demo_data

                seed_demo_data()
                logger.info("Baseline demo dataset initialized successfully.")
    except Exception as exc:
        logger.warning("Auto-seed on startup notice: %s", exc)

    # 5. Launch background ephemeral sandbox cleaner
    cleanup_task = asyncio.create_task(_cleanup_ephemeral_sandbox_cases())

    logger.info(
        "Application '%s' (v%s) started in '%s' environment.",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
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
        allow_origin_regex=r"https://.*\.vercel\.app",
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
