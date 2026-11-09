"""Domain identity and timestamp generation helpers ensuring UTC consistency."""

import secrets
import uuid
from datetime import UTC, datetime


def generate_id() -> str:
    """Generate a standard UUID4 string for entity primary keys."""
    return str(uuid.uuid4())


def generate_case_reference() -> str:
    """Generate human-readable unique case reference, e.g. CASE-20261107-A9F2."""
    date_str = datetime.now(UTC).strftime("%Y%m%d")
    random_suffix = secrets.token_hex(2).upper()
    return f"CASE-{date_str}-{random_suffix}"


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)
