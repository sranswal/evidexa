"""Cryptographic JWT access token and opaque refresh token services."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from document_intelligence.core.config import settings
from document_intelligence.core.exceptions import AuthenticationException
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.auth import TokenPayload


class TokenService:
    """JWT access token and secure refresh token lifecycle manager."""

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str | None = None,
        access_token_expire_minutes: int | None = None,
        refresh_token_expire_days: int | None = None,
        issuer: str | None = None,
        audience: str | None = None,
    ) -> None:
        self.secret_key = secret_key or settings.jwt_secret_key
        self.algorithm = algorithm or settings.jwt_algorithm
        self.access_token_expire_minutes = (
            access_token_expire_minutes or settings.access_token_expire_minutes
        )
        self.refresh_token_expire_days = (
            refresh_token_expire_days or settings.refresh_token_expire_days
        )
        self.issuer = issuer or settings.jwt_issuer
        self.audience = audience or settings.jwt_audience

    def create_access_token(
        self,
        user_id: str,
        email: str,
        username: str,
        system_role: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> tuple[str, int]:
        """Generate a signed, short-lived JWT access token."""
        now = datetime.now(UTC)
        exp = now + timedelta(minutes=self.access_token_expire_minutes)
        expires_in = int(self.access_token_expire_minutes * 60)

        payload: dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "username": username,
            "system_role": system_role,
            "iss": self.issuer,
            "aud": self.audience,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "jti": generate_id(),
        }
        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token, expires_in

    def decode_access_token(self, token: str) -> TokenPayload:
        """Verify and decode a JWT access token, strictly checking expiration."""
        try:
            decode_kwargs: dict[str, Any] = {
                "algorithms": [self.algorithm],
                "options": {"require": ["exp", "iat", "sub"]},
            }
            if self.audience:
                decode_kwargs["audience"] = self.audience
            if self.issuer:
                decode_kwargs["issuer"] = self.issuer

            # Attempt verification with audience and issuer
            try:
                payload = jwt.decode(token, self.secret_key, **decode_kwargs)
            except (jwt.InvalidAudienceError, jwt.InvalidIssuerError):
                # Fallback without issuer/audience verification for backward-compatibility with tokens issued without them
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=[self.algorithm],
                    options={
                        "require": ["exp", "iat", "sub"],
                        "verify_aud": False,
                        "verify_iss": False,
                    },
                )
            return TokenPayload(
                sub=payload["sub"],
                email=payload.get("email", ""),
                username=payload.get("username", ""),
                system_role=payload.get("system_role", "USER"),
                exp=payload["exp"],
                iat=payload["iat"],
                jti=payload.get("jti", ""),
                iss=payload.get("iss"),
                aud=payload.get("aud"),
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthenticationException("Access token has expired.") from e
        except jwt.InvalidTokenError as e:
            raise AuthenticationException("Invalid access token.") from e

    @staticmethod
    def create_refresh_token() -> str:
        """Generate an unguessable 48-byte cryptographically secure random token."""
        return secrets.token_urlsafe(48)

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        """Compute SHA-256 hash of refresh token for safe database persistence."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
