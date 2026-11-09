"""Core foundational utilities, configuration, logging, and security."""

from document_intelligence.core.config import Settings, settings
from document_intelligence.core.exceptions import (
    EntityNotFoundException,
    ForensicException,
    NotFoundException,
    PlatformException,
    SecurityException,
    ValidationException,
)
from document_intelligence.core.logging import get_logger, setup_logging

__all__ = [
    "Settings",
    "settings",
    "PlatformException",
    "EntityNotFoundException",
    "NotFoundException",
    "ForensicException",
    "ValidationException",
    "SecurityException",
    "setup_logging",
    "get_logger",
]
