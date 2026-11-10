"""Thread-safe bounded rate limiter for authentication endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

from document_intelligence.core.config import settings


class AuthRateLimiter:
    """Sliding-window in-memory rate limiter protecting login and token endpoints."""

    def __init__(
        self,
        max_attempts: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        self.max_attempts = max_attempts or settings.auth_rate_limit_attempts
        self.window_seconds = window_seconds or settings.auth_rate_limit_window_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = defaultdict(list)

    def is_rate_limited(self, identifier: str) -> bool:
        """Check if the given identifier (IP or username) has exceeded the threshold."""
        now = time.time()
        with self._lock:
            # Clean expired attempts
            cutoff = now - self.window_seconds
            attempts = [t for t in self._failures[identifier] if t > cutoff]
            self._failures[identifier] = attempts
            return len(attempts) >= self.max_attempts

    def record_failure(self, identifier: str) -> int:
        """Record a failed authentication attempt."""
        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            attempts = [t for t in self._failures[identifier] if t > cutoff]
            attempts.append(now)
            self._failures[identifier] = attempts
            return len(attempts)

    def record_success(self, identifier: str) -> None:
        """Reset failed attempts upon successful login."""
        with self._lock:
            self._failures.pop(identifier, None)

    def get_remaining_lockout_seconds(self, identifier: str) -> int:
        """Calculate seconds until lockout expires."""
        now = time.time()
        with self._lock:
            cutoff = now - self.window_seconds
            attempts = [t for t in self._failures.get(identifier, []) if t > cutoff]
            if not attempts:
                return 0
            oldest_relevant = attempts[0]
            remaining = int((oldest_relevant + self.window_seconds) - now)
            return max(remaining, 1)


# Global singleton rate limiter
auth_rate_limiter = AuthRateLimiter()
