"""Document ingestion and safe storage application service."""

from pathlib import Path
from typing import BinaryIO

from document_intelligence.core.config import Settings, settings
from document_intelligence.core.exceptions import (
    EntityNotFoundException,
    SecurityException,
    StorageException,
    ValidationException,
)
from document_intelligence.core.security import (
    ALLOWED_EXTENSIONS,
    sanitize_filename,
    validate_file_signature,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    DocumentType,
    EntityType,
    IngestionStatus,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.document import Document
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.storage.interface import DocumentStorageProtocol
from document_intelligence.modules.audit.ledger import AuditLedgerService


class DocumentService:
    """Application service for secure document ingestion and metadata management."""

    def __init__(
        self,
        case_repo: CaseRepository,
        document_repo: DocumentRepository,
        storage: DocumentStorageProtocol,
        audit_service: AuditLedgerService,
        app_settings: Settings = settings,
    ) -> None:
        self.case_repo = case_repo
        self.document_repo = document_repo
        self.storage = storage
        self.audit_service = audit_service
        self.settings = app_settings

    def ingest_document(
        self,
        case_id: str,
        file_obj: BinaryIO,
        declared_filename: str,
        declared_media_type: str,
        created_by: str | None = None,
    ) -> Document:
        """Ingest, validate, store, and register an uploaded document."""
        # 1. Verify case exists and is not archived
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case", case_id)
        if case.status == CaseStatus.ARCHIVED:
            raise ValidationException(
                f"Cannot ingest documents into archived case '{case_id}'.",
                details={"case_id": case_id, "status": case.status.value},
            )

        # 2. Validate declared media type
        clean_name = sanitize_filename(declared_filename)
        ext = Path(clean_name).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise SecurityException(
                f"File extension '{ext}' is not supported. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            )

        if declared_media_type not in self.settings.allowed_media_types:
            raise SecurityException(
                f"Media type '{declared_media_type}' is not allowed. Allowed: {self.settings.allowed_media_types}"
            )

        # 3. Read header bytes to verify magic signature
        header = file_obj.read(16)
        file_obj.seek(0)

        if not validate_file_signature(header, declared_media_type):
            raise SecurityException(
                f"File content signature does not match declared media type '{declared_media_type}'."
            )

        # 4. Generate unique document identity
        document_id = generate_id()

        # 5. Write atomically to storage
        storage_key, size_bytes, sha256_hex = self.storage.store_original(
            case_id=case_id,
            document_id=document_id,
            file_obj=file_obj,
            declared_filename=clean_name,
        )

        # 6. Check for duplicate SHA-256 in the same case
        existing_doc = self.document_repo.get_by_sha256(case_id, sha256_hex)
        doc_metadata: dict[str, str] = {}
        if existing_doc:
            doc_metadata["duplicate_of_document_id"] = existing_doc.id

        document = Document(
            id=document_id,
            case_id=case_id,
            original_filename=clean_name,
            media_type=declared_media_type,
            file_extension=ext,
            file_size_bytes=size_bytes,
            sha256=sha256_hex,
            storage_key=storage_key,
            document_type=DocumentType.UNKNOWN,
            ingestion_status=IngestionStatus.STORED,
            created_by=created_by,
            metadata=doc_metadata,
        )

        try:
            saved_doc = self.document_repo.save(document)

            # Record audit events
            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.DOCUMENT_INGESTED,
                entity_type=EntityType.DOCUMENT,
                entity_id=saved_doc.id,
                payload={
                    "original_filename": saved_doc.original_filename,
                    "media_type": saved_doc.media_type,
                    "file_size_bytes": saved_doc.file_size_bytes,
                    "is_duplicate": bool(existing_doc),
                },
                actor_id=created_by,
            )

            self.audit_service.record_event(
                case_id=case_id,
                event_type=AuditEventType.FILE_HASH_REGISTERED,
                entity_type=EntityType.DOCUMENT,
                entity_id=saved_doc.id,
                payload={"sha256": saved_doc.sha256},
                actor_id=created_by,
            )

            return saved_doc

        except Exception as exc:
            # Transaction compensation: Delete stored file if DB save fails
            self.storage.delete_original(storage_key)
            raise StorageException(f"Failed to register document in database: {exc}") from exc

    def list_documents(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """List documents in a case."""
        case = self.case_repo.get_by_id(case_id)
        if not case:
            raise EntityNotFoundException("Case", case_id)
        return self.document_repo.list_by_case(case_id, skip=skip, limit=limit)
