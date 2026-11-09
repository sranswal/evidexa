"""Integration tests for FilesystemDocumentStorage and storage safeguards."""

import io

import pytest

from document_intelligence.core.config import Settings
from document_intelligence.core.exceptions import SecurityException, StorageException
from document_intelligence.core.security import calculate_sha256, sanitize_filename
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage


class TestStorageSanitization:
    """Test filename sanitization against path traversal and dangerous characters."""

    def test_sanitize_filename_strips_traversal(self) -> None:
        assert sanitize_filename("../../etc/passwd") == "passwd"
        assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
        assert sanitize_filename("safe_document.pdf") == "safe_document.pdf"
        assert sanitize_filename("") == "unnamed_document"
        assert sanitize_filename("   ") == "unnamed_document"


class TestFilesystemDocumentStorage:
    """Test atomic storage, size limits, and SHA-256 calculation."""

    def test_store_and_retrieve_original(self, test_storage: FilesystemDocumentStorage) -> None:
        content = b"%PDF-1.4 Mock synthetic PDF bytes for testing storage"
        expected_sha = calculate_sha256(content)

        file_obj = io.BytesIO(content)
        storage_key, size, sha = test_storage.store_original(
            case_id="case-test-1",
            document_id="doc-test-1",
            file_obj=file_obj,
            declared_filename="sample.pdf",
        )

        assert size == len(content)
        assert sha == expected_sha
        assert storage_key.endswith(".pdf")

        # Verify physical file existence and content
        file_path = test_storage.get_original_path(storage_key)
        assert file_path.exists()
        assert file_path.read_bytes() == content

    def test_empty_file_rejected(self, test_storage: FilesystemDocumentStorage) -> None:
        empty_obj = io.BytesIO(b"")
        with pytest.raises(StorageException, match="Cannot ingest empty file"):
            test_storage.store_original(
                case_id="case-1",
                document_id="doc-1",
                file_obj=empty_obj,
                declared_filename="empty.pdf",
            )

    def test_oversized_file_rejected(self, test_settings: Settings) -> None:
        # Settings limit is 1 MB
        storage = FilesystemDocumentStorage(app_settings=test_settings)
        oversized_data = b"X" * (test_settings.max_upload_size_bytes + 1024)

        with pytest.raises(SecurityException, match="exceeds maximum allowed size"):
            storage.store_original(
                case_id="case-1",
                document_id="doc-oversized",
                file_obj=io.BytesIO(oversized_data),
                declared_filename="huge.pdf",
            )

    def test_path_traversal_detection(self, test_storage: FilesystemDocumentStorage) -> None:
        with pytest.raises(SecurityException, match="Path traversal attempt detected"):
            test_storage.get_original_path("../../sensitive_system_file")

    def test_failed_upload_cleans_up_temporary_files(self, test_settings: Settings) -> None:
        """When an upload fails due to size limits, all temporary staging files are cleaned up."""
        storage = FilesystemDocumentStorage(app_settings=test_settings)
        oversized = b"A" * (test_settings.max_upload_size_bytes + 2048)

        # Before test: count files in temp_dir
        initial_temp_files = list(test_settings.temp_dir.glob("*.upload"))

        with pytest.raises(SecurityException):
            storage.store_original(
                case_id="case-fail-cleanup",
                document_id="doc-failed-upload",
                file_obj=io.BytesIO(oversized),
                declared_filename="fail.pdf",
            )

        # Verify no stranded .upload files in temp_dir
        final_temp_files = list(test_settings.temp_dir.glob("*.upload"))
        assert len(final_temp_files) == len(initial_temp_files)
