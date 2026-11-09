"""Platform exception hierarchy and standard error codes."""

from typing import Any


class PlatformException(Exception):
    """Base class for all domain and platform exceptions."""

    def __init__(
        self,
        message: str,
        code: str = "PLATFORM_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class EntityNotFoundException(PlatformException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        entity_type: str,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        msg = f"{entity_type} with ID '{entity_id}' not found." if entity_id else entity_type
        det = details or {}
        if entity_id:
            det = {**det, "entity_type": entity_type, "entity_id": entity_id}
        super().__init__(
            message=msg,
            code="ENTITY_NOT_FOUND",
            details=det,
        )


NotFoundException = EntityNotFoundException


class ConflictException(PlatformException):
    """Raised when an entity conflict occurs (e.g. duplicate reference)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="CONFLICT_ERROR", details=details)


class ValidationException(PlatformException):
    """Raised when domain business invariants are violated."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", details=details)


class InvalidStatusTransitionException(ValidationException):
    """Raised when an illegal lifecycle state transition is attempted."""

    def __init__(self, entity: str, current_status: str, target_status: str) -> None:
        super().__init__(
            message=f"Cannot transition {entity} from '{current_status}' to '{target_status}'.",
            details={
                "entity": entity,
                "current_status": current_status,
                "target_status": target_status,
            },
        )
        self.code = "INVALID_STATUS_TRANSITION"


class SecurityException(PlatformException):
    """Raised when a security rule is violated (e.g. path traversal, magic byte mismatch)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="SECURITY_VIOLATION", details=details)


class StorageException(PlatformException):
    """Raised when file storage operations fail."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="STORAGE_ERROR", details=details)


class AuditChainException(PlatformException):
    """Raised when audit ledger tampering or broken chain integrity is detected."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="AUDIT_CHAIN_INTEGRITY_FAILURE", details=details)


class ForensicException(PlatformException):
    """Raised when forensic analysis fails."""

    def __init__(
        self, message: str, code: str = "FORENSIC_ERROR", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message=message, code=code, details=details)
