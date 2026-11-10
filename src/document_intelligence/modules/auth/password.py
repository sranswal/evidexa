"""Secure password hashing using Argon2id."""

from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

logger = logging.getLogger(__name__)


class PasswordService:
    """Argon2id password hashing and verification service."""

    def __init__(self) -> None:
        # RFC 9106 recommended parameters:
        # time_cost=3, memory_cost=65536 (64 MiB), parallelism=4, hash_len=32
        self._hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
        )

    def hash_password(self, plain_password: str) -> str:
        """Hash a plaintext password using Argon2id."""
        if not plain_password:
            raise ValueError("Password cannot be empty.")
        return self._hasher.hash(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plaintext password against an Argon2id hash in constant-time."""
        if not plain_password or not hashed_password:
            return False
        try:
            return self._hasher.verify(hashed_password, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
        except Exception as e:
            logger.warning("Unexpected error during password verification: %s", type(e).__name__)
            return False

    def check_needs_rehash(self, hashed_password: str) -> bool:
        """Check if hash parameters are outdated."""
        try:
            return self._hasher.check_needs_rehash(hashed_password)
        except Exception:
            return True
