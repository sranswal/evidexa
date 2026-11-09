"""Filesystem implementation of DocumentStorageProtocol with atomic write and safeguards."""

import hashlib
import os
import secrets
import shutil
from pathlib import Path
from typing import BinaryIO

from document_intelligence.core.config import Settings, settings
from document_intelligence.core.exceptions import (
    ConflictException,
    SecurityException,
    StorageException,
)
from document_intelligence.core.security import ensure_safe_path, sanitize_filename
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol


class FilesystemDocumentStorage(DocumentStorageProtocol):
    """Stores original uploaded documents and artifacts on local filesystem."""

    def __init__(self, app_settings: Settings = settings) -> None:
        self.settings = app_settings
        self.settings.ensure_directories()
        self.originals_dir = self.settings.originals_dir
        self.artifacts_dir = self.settings.artifacts_dir
        self.temp_dir = self.settings.temp_dir

    def store_original(
        self,
        case_id: str,
        document_id: str,
        file_obj: BinaryIO,
        declared_filename: str,
    ) -> tuple[str, int, str]:
        """Store document atomically: stream to temp file, calculate SHA-256, then rename."""
        clean_name = sanitize_filename(declared_filename)
        ext = Path(clean_name).suffix.lower()

        # Storage key is isolated by case_id and uses document_id to prevent collision
        storage_rel_path = Path(case_id) / f"{document_id}{ext}"
        destination_path = self.originals_dir / storage_rel_path

        # Guard against path traversal
        ensure_safe_path(self.originals_dir, destination_path)

        # Ensure case directory exists
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        # Guard against accidental overwrites
        if destination_path.exists():
            raise ConflictException(
                f"Document already exists at storage destination: {storage_rel_path}"
            )

        temp_suffix = secrets.token_hex(4)
        temp_file_path = self.temp_dir / f"tmp_{document_id}_{temp_suffix}.upload"

        hasher = hashlib.sha256()
        bytes_written = 0
        chunk_size = 64 * 1024  # 64 KB chunks

        try:
            with open(temp_file_path, "wb") as temp_out:
                while True:
                    chunk = file_obj.read(chunk_size)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if bytes_written > self.settings.max_upload_size_bytes:
                        raise SecurityException(
                            f"Uploaded file exceeds maximum allowed size of {self.settings.max_upload_size_bytes} bytes."
                        )
                    hasher.update(chunk)
                    temp_out.write(chunk)

            if bytes_written == 0:
                raise StorageException("Cannot ingest empty file (0 bytes).")

            # Atomic move from temp to final destination
            shutil.move(str(temp_file_path), str(destination_path))

            # Set OS-level read-only permissions on stored original document to prevent tampering
            try:
                os.chmod(destination_path, 0o444)
            except OSError:
                pass

        except Exception as exc:
            # Clean up temp file on failure
            if temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except OSError:
                    pass
            if isinstance(exc, (ConflictException, SecurityException, StorageException)):
                raise
            raise StorageException(f"Failed to store file: {exc}") from exc

        sha256_hex = hasher.hexdigest().lower()
        storage_key = str(storage_rel_path).replace("\\", "/")

        return storage_key, bytes_written, sha256_hex

    def get_original_path(self, storage_key: str) -> Path:
        """Resolve absolute path, validating against path traversal."""
        target = self.originals_dir / storage_key
        return ensure_safe_path(self.originals_dir, target)

    def delete_original(self, storage_key: str) -> None:
        """Safely delete original file for transaction compensation."""
        try:
            path = self.get_original_path(storage_key)
            if path.exists() and path.is_file():
                try:
                    os.chmod(path, 0o666)
                except OSError:
                    pass
                os.remove(path)
        except Exception:
            # Best-effort compensation cleanup
            pass

    def create_analysis_snapshot(
        self, storage_key: str, processing_run_id: str
    ) -> tuple[Path, str]:
        """Create a controlled, ephemeral copy of an original document for forensic analysis.

        Guarantees:
        - Resolves and verifies the original stored document.
        - Concurrently computes source SHA-256 and writes to a unique temporary file.
        - Calculates the snapshot SHA-256 and verifies it matches the source read hash.
        - Returns (snapshot_path, snapshot_sha256).
        """
        source_path = self.get_original_path(storage_key)
        if not source_path.exists() or not source_path.is_file():
            raise StorageException(f"Original document not found at storage key: {storage_key}")

        token = secrets.token_hex(4)
        ext = source_path.suffix.lower() or ".pdf"
        snapshot_filename = f"snapshot_{processing_run_id}_{token}{ext}"
        snapshot_path = self.temp_dir / snapshot_filename
        ensure_safe_path(self.temp_dir, snapshot_path)

        source_hasher = hashlib.sha256()
        snapshot_hasher = hashlib.sha256()
        chunk_size = 64 * 1024

        try:
            with open(source_path, "rb") as src, open(snapshot_path, "wb") as dst:
                while chunk := src.read(chunk_size):
                    source_hasher.update(chunk)
                    dst.write(chunk)
                    snapshot_hasher.update(chunk)

            src_hash = source_hasher.hexdigest().lower()
            snap_hash = snapshot_hasher.hexdigest().lower()

            if src_hash != snap_hash:
                raise SecurityException(
                    "Integrity error during snapshot creation: hash divergence."
                )

            return snapshot_path, snap_hash

        except Exception:
            if snapshot_path.exists():
                try:
                    snapshot_path.unlink()
                except OSError:
                    pass
            raise

    def cleanup_analysis_snapshot(self, snapshot_path: Path) -> None:
        """Safely remove ephemeral analysis snapshot."""
        try:
            safe_target = ensure_safe_path(self.temp_dir, snapshot_path)
            if safe_target.exists() and safe_target.is_file():
                try:
                    os.chmod(safe_target, 0o666)
                except OSError:
                    pass
                safe_target.unlink()
        except Exception:
            pass

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
        - Strict path traversal prevention.
        - Hierarchical storage: {case_id}/{document_id}/{processing_run_id}/{filename}
        - Separation from original documents.
        - Synchronous SHA-256 calculation.
        - Returns (artifact_key, sha256_hex).
        """
        clean_name = sanitize_filename(artifact_filename)
        artifact_rel_path = Path(case_id) / document_id / processing_run_id / clean_name
        dest_path = self.artifacts_dir / artifact_rel_path

        # Guard against path traversal
        ensure_safe_path(self.artifacts_dir, dest_path)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256(data)
        sha256_hex = hasher.hexdigest().lower()

        temp_file = dest_path.parent / f".tmp_{secrets.token_hex(4)}_{clean_name}"
        try:
            with open(temp_file, "wb") as f:
                f.write(data)
            shutil.move(str(temp_file), str(dest_path))
        except Exception as exc:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise StorageException(f"Failed to store artifact: {exc}") from exc

        artifact_key = str(artifact_rel_path).replace("\\", "/")
        return artifact_key, sha256_hex

    def get_artifact_path(self, artifact_key: str) -> Path:
        """Resolve filesystem path for a stored artifact, validating against path traversal."""
        target = self.artifacts_dir / artifact_key
        return ensure_safe_path(self.artifacts_dir, target)

    def delete_artifact(self, artifact_key: str) -> None:
        """Safely delete stored artifact (used for cleanup on processing run failure)."""
        try:
            path = self.get_artifact_path(artifact_key)
            if path.exists() and path.is_file():
                try:
                    os.chmod(path, 0o666)
                except OSError:
                    pass
                os.remove(path)
        except Exception:
            pass
