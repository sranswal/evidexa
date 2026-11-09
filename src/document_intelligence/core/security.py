"""Security utilities, file signature inspection, and sanitization safeguards."""

import hashlib
import re
from pathlib import Path

from document_intelligence.core.exceptions import SecurityException

# Recognized file signatures (magic bytes)
MAGIC_SIGNATURES = {
    "application/pdf": [b"%PDF-"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/tiff": [b"II*\x00", b"MM\x00*"],
}

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

WINDOWS_RESERVED_NAMES: set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(filename: str) -> str:
    """Sanitize user-provided filename, eliminating path traversal and dangerous characters.

    Never trusts the user-supplied filename as an absolute or relative path.
    Neutralizes Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    """
    if not filename or not filename.strip():
        return "unnamed_document"

    # Strip directory components (both Unix and Windows slashes)
    clean_name = filename.replace("\\", "/").split("/")[-1]

    # Remove null bytes, control characters, and dangerous characters
    clean_name = re.sub(r"[\x00-\x1f\x7f\"'<>|:*?]", "", clean_name)
    clean_name = clean_name.strip(" .")

    if not clean_name:
        return "unnamed_document"

    # Neutralize Windows reserved device names
    stem = Path(clean_name).stem.upper()
    if stem in WINDOWS_RESERVED_NAMES:
        clean_name = f"doc_{clean_name}"

    return clean_name[:255]


def validate_file_signature(header_bytes: bytes, declared_media_type: str) -> bool:
    """Inspect magic bytes to confirm declared media type.

    Does not trust file extension or Content-Type header alone.
    """
    expected_signatures = MAGIC_SIGNATURES.get(declared_media_type)
    if not expected_signatures:
        return False

    return any(header_bytes.startswith(sig) for sig in expected_signatures)


def ensure_safe_path(base_dir: Path, target_path: Path) -> Path:
    """Verify that target_path resolves strictly within base_dir, preventing path traversal."""
    resolved_base = base_dir.resolve()
    resolved_target = target_path.resolve()

    # Normalize Windows extended-length path prefix (\\?\) which resolve() can produce for non-existent paths
    base_str = str(resolved_base)
    target_str = str(resolved_target)
    if base_str.startswith(("\\\\?\\", "//?/")):
        base_str = base_str[4:]
    if target_str.startswith(("\\\\?\\", "//?/")):
        target_str = target_str[4:]

    norm_base = Path(base_str)
    norm_target = Path(target_str)

    try:
        norm_target.relative_to(norm_base)
    except ValueError as exc:
        raise SecurityException(
            message="Path traversal attempt detected.",
            details={"attempted_path": str(target_path)},
        ) from exc

    return resolved_target


def calculate_sha256(data: bytes) -> str:
    """Calculate hex-encoded SHA-256 digest of data bytes."""
    return hashlib.sha256(data).hexdigest()


def mask_sensitive_value(value: str | None) -> str:
    """Mask sensitive string content for logging and display."""
    if not value:
        return ""
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}***{value[-2:]}"
