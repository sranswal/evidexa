"""Repository interface and SQLAlchemy implementation for Document entities."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from document_intelligence.domain.enums import DocumentType, IngestionStatus
from document_intelligence.domain.models.document import Document
from document_intelligence.infrastructure.persistence.models import DocumentModel


class DocumentRepository:
    """Repository handling persistence and retrieval of Document entities."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def save(self, doc: Document) -> Document:
        """Persist or update Document entity."""
        existing = self.db.get(DocumentModel, doc.id)
        if existing:
            existing.page_count = doc.page_count
            existing.document_type = doc.document_type.value if doc.document_type else "UNKNOWN"
            existing.ingestion_status = doc.ingestion_status.value
            existing.doc_metadata = doc.metadata
        else:
            model = DocumentModel(
                id=doc.id,
                case_id=doc.case_id,
                original_filename=doc.original_filename,
                media_type=doc.media_type,
                file_extension=doc.file_extension,
                file_size_bytes=doc.file_size_bytes,
                sha256=doc.sha256,
                storage_key=doc.storage_key,
                page_count=doc.page_count,
                document_type=doc.document_type.value if doc.document_type else "UNKNOWN",
                ingestion_status=doc.ingestion_status.value,
                created_at=doc.created_at,
                created_by=doc.created_by,
                doc_metadata=doc.metadata,
            )
            self.db.add(model)
        self.db.commit()
        return doc

    def get_by_id(self, document_id: str) -> Document | None:
        """Retrieve Document by ID."""
        model = self.db.get(DocumentModel, document_id)
        if not model:
            return None
        return self._to_domain(model)

    def get_by_sha256(self, case_id: str, sha256: str) -> Document | None:
        """Check if an identical document hash already exists in this case."""
        stmt = (
            select(DocumentModel)
            .where(DocumentModel.case_id == case_id)
            .where(DocumentModel.sha256 == sha256.lower())
        )
        model = self.db.scalar(stmt)
        if not model:
            return None
        return self._to_domain(model)

    def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Document], int]:
        """List documents in a case with pagination."""
        stmt = select(DocumentModel).where(DocumentModel.case_id == case_id)
        total = len(list(self.db.scalars(stmt).all()))

        paginated_stmt = stmt.order_by(DocumentModel.created_at.desc()).offset(skip).limit(limit)
        models = self.db.scalars(paginated_stmt).all()

        return [self._to_domain(m) for m in models], total

    @staticmethod
    def _to_domain(m: DocumentModel) -> Document:
        return Document(
            id=m.id,
            case_id=m.case_id,
            original_filename=m.original_filename,
            media_type=m.media_type,
            file_extension=m.file_extension,
            file_size_bytes=m.file_size_bytes,
            sha256=m.sha256,
            storage_key=m.storage_key,
            page_count=m.page_count,
            document_type=DocumentType(m.document_type)
            if m.document_type in DocumentType._value2member_map_
            else DocumentType.UNKNOWN,
            ingestion_status=IngestionStatus(m.ingestion_status),
            created_at=m.created_at,
            created_by=m.created_by,
            metadata=dict(m.doc_metadata or {}),
        )
