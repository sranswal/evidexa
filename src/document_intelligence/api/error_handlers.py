"""Global exception handlers mapping domain exceptions to consistent RFC-style JSON envelopes."""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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
from document_intelligence.core.logging import get_logger

logger = get_logger(__name__)


def make_error_response(status_code: int, code: str, message: str, details: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
            }
        },
    )


async def entity_not_found_handler(request: Request, exc: EntityNotFoundException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def conflict_handler(request: Request, exc: ConflictException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_409_CONFLICT,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_handler(request: Request, exc: ValidationException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def security_handler(request: Request, exc: SecurityException) -> JSONResponse:
    logger.warning("Security violation: %s - %s", exc.message, exc.details)
    return make_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def authentication_handler(request: Request, exc: AuthenticationException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def forbidden_handler(request: Request, exc: ForbiddenException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_403_FORBIDDEN,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def rate_limit_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    return make_error_response(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def storage_handler(request: Request, exc: StorageException) -> JSONResponse:
    logger.error("Storage error: %s - %s", exc.message, exc.details)
    return make_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code=exc.code,
        message="A storage operation error occurred.",
        details={},
    )


async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    return make_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="REQUEST_VALIDATION_ERROR",
        message="Invalid request payload.",
        details={"validation_errors": errors},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server exception: %s", exc)
    return make_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred.",
        details={},
    )
