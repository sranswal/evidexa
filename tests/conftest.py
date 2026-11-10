"""Pytest configuration and test fixtures."""

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from document_intelligence.api.dependencies import get_current_user
from document_intelligence.core.config import Settings
from document_intelligence.domain.identifiers import utc_now
from document_intelligence.infrastructure.persistence.database import Base, get_db
from document_intelligence.infrastructure.persistence.models import UserModel
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage
from document_intelligence.main import create_app


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Provide isolated temporary directory cleaned up after test."""
    temp_path = Path(tempfile.mkdtemp(prefix="test_doc_intel_"))
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Settings configured for isolated testing."""
    return Settings(
        APP_ENV="test",
        DEBUG=True,
        DATA_DIR=temp_dir,
        DATABASE_URL=f"sqlite:///{temp_dir}/test.db",
        MAX_UPLOAD_SIZE_BYTES=1024 * 1024,  # 1 MB for testing
    )


@pytest.fixture
def test_storage(test_settings: Settings) -> FilesystemDocumentStorage:
    """Filesystem storage instance targeting test directory."""
    return FilesystemDocumentStorage(app_settings=test_settings)


@pytest.fixture
def db_session(test_settings: Settings) -> Generator[Session, None, None]:
    """Isolated database session using fresh SQLite file."""
    test_settings.ensure_directories()
    engine = create_engine(test_settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(test_settings: Settings, db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with overridden test dependencies."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    default_admin = UserModel(
        id="usr-system-admin-001",
        email="admin@evidexa.test",
        username="admin",
        hashed_password="argon2id_mock_hash",
        full_name="Default System Admin",
        is_active=True,
        system_role="SYSTEM_ADMIN",
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db_session.add(default_admin)
    db_session.commit()

    def override_get_current_user() -> UserModel:
        return default_admin

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    with TestClient(app) as test_client:
        yield test_client
