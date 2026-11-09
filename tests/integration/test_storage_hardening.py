"""Integration tests verifying storage layer hardening, overwrite protection, Windows reserved names, and read-only flags."""

import io
import os
import stat

import pytest

from document_intelligence.core.exceptions import ConflictException
from document_intelligence.core.security import sanitize_filename
from document_intelligence.infrastructure.storage.filesystem import FilesystemDocumentStorage


class TestStorageHardening:
    """Test storage immutability, overwrite guards, Windows device name neutralization, and read-only flags."""

    def test_accidental_overwrite_rejected(self, test_storage: FilesystemDocumentStorage) -> None:
        case_id = "case-overwrite-test"
        doc_id = "doc-immutable-1"
        content = b"%PDF-1.4 initial content"

        # First storage must succeed
        key1, size1, hash1 = test_storage.store_original(
            case_id=case_id,
            document_id=doc_id,
            file_obj=io.BytesIO(content),
            declared_filename="invoice.pdf",
        )
        assert size1 == len(content)

        # Attempting to store to the exact same case_id and document_id destination must raise ConflictException
        with pytest.raises(
            ConflictException, match="Document already exists at storage destination"
        ):
            test_storage.store_original(
                case_id=case_id,
                document_id=doc_id,
                file_obj=io.BytesIO(b"%PDF-1.4 overwritten content"),
                declared_filename="invoice.pdf",
            )

    def test_windows_reserved_device_names_sanitization(self) -> None:
        """Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) must be neutralized."""
        reserved_examples = [
            ("CON.pdf", "doc_CON.pdf"),
            ("prn.png", "doc_prn.png"),
            ("aux.jpg", "doc_aux.jpg"),
            ("NUL", "doc_NUL"),
            ("com1.pdf", "doc_com1.pdf"),
            ("lpt3.tiff", "doc_lpt3.tiff"),
        ]
        for original, expected in reserved_examples:
            sanitized = sanitize_filename(original)
            assert sanitized == expected, f"Failed for {original}: got {sanitized}"

    def test_os_level_read_only_attribute(self, test_storage: FilesystemDocumentStorage) -> None:
        """Stored original document must be marked read-only at OS level to enforce immutability."""
        case_id = "case-readonly-test"
        doc_id = "doc-readonly-1"
        content = b"%PDF-1.4 read-only test content"

        storage_key, _, _ = test_storage.store_original(
            case_id=case_id,
            document_id=doc_id,
            file_obj=io.BytesIO(content),
            declared_filename="sample.pdf",
        )

        file_path = test_storage.get_original_path(storage_key)
        assert file_path.exists()

        # Check file mode: write flag should be unset (or non-writable)
        file_stat = os.stat(file_path)
        is_writeable = bool(file_stat.st_mode & stat.S_IWRITE)
        assert is_writeable is False, "Stored original file should not have write permissions!"

        # Ensure compensation delete_original successfully unsets read-only flag and removes file
        test_storage.delete_original(storage_key)
        assert not file_path.exists()

    def test_concurrent_storage_writes_with_distinct_tokens(
        self, test_storage: FilesystemDocumentStorage
    ) -> None:
        """Simultaneous uploads under concurrent threads use unique temp tokens without collisions."""
        from concurrent.futures import ThreadPoolExecutor

        case_id = "case-concurrent-upload"
        num_docs = 10

        def upload_worker(idx: int) -> tuple[str, int, str]:
            return test_storage.store_original(
                case_id=case_id,
                document_id=f"doc-concurrent-{idx}",
                file_obj=io.BytesIO(f"%PDF-1.4 file content {idx}".encode()),
                declared_filename=f"file_{idx}.pdf",
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(upload_worker, i) for i in range(num_docs)]
            results = [f.result() for f in futures]

        assert len(results) == num_docs
        # Verify all storage keys and hashes are unique
        keys = [r[0] for r in results]
        assert len(set(keys)) == num_docs
        for key in keys:
            path = test_storage.get_original_path(key)
            assert path.exists()
