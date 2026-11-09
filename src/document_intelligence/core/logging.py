"""Structured logging configuration with PII/content protection filters."""

import logging
import sys
from typing import Any


class SafeLogFormatter(logging.Formatter):
    """Formatter that strips or sanitizes sensitive fields before output."""

    SENSITIVE_KEYS = {"password", "secret", "token", "raw_value", "ocr_text", "aadhaar", "pan"}

    def format(self, record: logging.LogRecord) -> str:
        # If extra parameters contain sensitive keys, sanitize them
        if hasattr(record, "details") and isinstance(record.details, dict):  # type: ignore[attr-defined]
            record.details = self._sanitize_dict(record.details)  # type: ignore[attr-defined]
        return super().format(record)

    def _sanitize_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        sanitized: dict[str, Any] = {}
        for k, v in d.items():
            if any(s in k.lower() for s in self.SENSITIVE_KEYS):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_dict(v)
            else:
                sanitized[k] = v
        return sanitized


def setup_logging(log_level: str = "INFO") -> None:
    """Initialize structured application logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = SafeLogFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if called multiple times
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Retrieve named logger."""
    return logging.getLogger(name)
