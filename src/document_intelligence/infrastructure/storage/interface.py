"""Document storage abstraction protocol."""

from pathlib import Path
from typing import BinaryIO, Protocol


class DocumentStorageProtocol(Protocol):
    """Protocol defining storage operations for original files and artifacts."""

    def store_original(
        self,
        case_id: str,
        document_id: str,
        file_obj: BinaryIO,
        declared_filename: str,
    ) -> tuple[str, int, str]:
        """Store original uploaded document atomically.

        Returns:
            Tuple of (storage_key, file_size_bytes, sha256_hex)
        """
        ...

    def get_original_path(self, storage_key: str) -> Path:
        """Resolve filesystem path for a stored original document."""
        ...

    def delete_original(self, storage_key: str) -> None:
        """Delete stored original (used for compensation on failed transactions)."""
        ...

    def create_analysis_snapshot(
        self, storage_key: str, processing_run_id: str
    ) -> tuple[Path, str]:
        """Create a controlled, ephemeral copy of an original document for forensic analysis.

        Returns:
            Tuple of (snapshot_path, snapshot_sha256_hex)
        """
        ...

    def cleanup_analysis_snapshot(self, snapshot_path: Path) -> None:
        """Safely remove ephemeral analysis snapshot."""
        ...

    def store_artifact(
        self,
        case_id: str,
        document_id: str,
        processing_run_id: str,
        artifact_filename: str,
        data: bytes,
    ) -> tuple[str, str]:
        """Store derived forensic artifact atomically in artifacts directory.

        Guarantees:
        - Path traversal prevention.
        - Hierarchical storage: {case_id}/{document_id}/{processing_run_id}/{filename}
        - Collision resistance and separation from original documents.
        - Returns (artifact_key, sha256_hex).
        """
        ...

    def get_artifact_path(self, artifact_key: str) -> Path:
        """Resolve filesystem path for a stored artifact, validating against path traversal."""
        ...

    def delete_artifact(self, artifact_key: str) -> None:
        """Safely delete stored artifact (used for cleanup on processing run failure)."""
        ...
