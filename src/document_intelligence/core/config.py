"""Application configuration using Pydantic Settings."""

from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Document Intelligence Platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EVIDEXA"
    app_version: str = "0.1.0"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Data & Persistence
    data_dir: Path = Field(default=Path("./data"), alias="DATA_DIR")
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")
    ocr_model_dir: Path = Field(default=Path("./data/models/ocr"), alias="OCR_MODEL_DIR")

    # Uploads & Ingestion
    max_upload_size_bytes: int = Field(
        default=50 * 1024 * 1024, alias="MAX_UPLOAD_SIZE_BYTES"
    )  # 50 MB
    allowed_media_types: list[str] = Field(
        default=["application/pdf", "image/png", "image/jpeg", "image/tiff"],
        alias="ALLOWED_MEDIA_TYPES",
    )

    # Server & Networking
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: list[str] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        alias="CORS_ORIGINS",
    )

    # LLM & Grounded Assistant Settings
    llm_provider: str = Field(default="mock", alias="LLM_PROVIDER")
    llm_api_base: str | None = Field(default=None, alias="LLM_API_BASE")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str = Field(default="grounded-evidexa-engine", alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=15.0, alias="LLM_TIMEOUT_SECONDS")

    # Enterprise Identity, Authentication & Security
    jwt_secret_key: str = Field(
        default="evidexa-super-secret-security-key-production-32-bytes-minimum!",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_issuer: str = Field(default="evidexa:auth", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="evidexa:api", alias="JWT_AUDIENCE")
    access_token_expire_minutes: int = Field(default=15, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=7, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    auth_rate_limit_attempts: int = Field(default=5, alias="AUTH_RATE_LIMIT_ATTEMPTS")
    auth_rate_limit_window_seconds: int = Field(default=900, alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax", alias="AUTH_COOKIE_SAMESITE"
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        if self.app_env.lower() in ("production", "prod"):
            insecure_defaults = {
                "evidexa-super-secret-security-key-production-32-bytes-minimum!",
                "secret",
                "changeme",
                "default",
                "password",
            }
            if self.jwt_secret_key in insecure_defaults or len(self.jwt_secret_key) < 32:
                raise ValueError(
                    "Insecure or default JWT_SECRET_KEY in production. A secure key with at least 32 characters is required."
                )
            if not self.auth_cookie_secure:
                raise ValueError("AUTH_COOKIE_SECURE must be True in production.")
        return self

    @field_validator("allowed_media_types", "cors_origins", mode="before")
    @classmethod
    def parse_comma_separated_list(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def artifacts_dir(self) -> Path:
        return self.data_dir / "artifacts"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    def ensure_directories(self) -> None:
        """Create necessary runtime directories."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.originals_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.ocr_model_dir.mkdir(parents=True, exist_ok=True)


# Global settings singleton
settings = Settings()
