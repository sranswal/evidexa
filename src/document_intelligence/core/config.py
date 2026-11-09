"""Application configuration using Pydantic Settings."""

from pathlib import Path

from pydantic import Field, field_validator
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
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        alias="CORS_ORIGINS",
    )

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


# Global settings singleton
settings = Settings()
