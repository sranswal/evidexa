"""Registry for structured extraction schemas indexed by ID and document class."""

from __future__ import annotations

from document_intelligence.domain.enums import DocumentClass
from document_intelligence.domain.models.extraction import ExtractionSchema
from document_intelligence.modules.understanding.extraction.schemas.bank_statement import (
    BANK_STATEMENT_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.invoice import (
    INVOICE_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.purchase_order import (
    PURCHASE_ORDER_SCHEMA_V1,
)
from document_intelligence.modules.understanding.extraction.schemas.receipt import (
    RECEIPT_SCHEMA_V1,
)


class SchemaRegistry:
    """Registry maintaining active extraction schemas."""

    def __init__(self) -> None:
        self._schemas_by_id: dict[str, ExtractionSchema] = {}
        self._schemas_by_class: dict[DocumentClass, list[ExtractionSchema]] = {}

        # Register default initial schemas
        self.register_schema(INVOICE_SCHEMA_V1)
        self.register_schema(RECEIPT_SCHEMA_V1)
        self.register_schema(PURCHASE_ORDER_SCHEMA_V1)
        self.register_schema(BANK_STATEMENT_SCHEMA_V1)

    def register_schema(self, schema: ExtractionSchema) -> None:
        """Register a new or updated extraction schema."""
        self._schemas_by_id[schema.schema_id] = schema
        if schema.document_class not in self._schemas_by_class:
            self._schemas_by_class[schema.document_class] = []
        # Update or append
        existing = [
            s
            for s in self._schemas_by_class[schema.document_class]
            if s.schema_id == schema.schema_id
        ]
        if existing:
            self._schemas_by_class[schema.document_class].remove(existing[0])
        self._schemas_by_class[schema.document_class].append(schema)

    def get_by_id(self, schema_id: str) -> ExtractionSchema | None:
        """Retrieve schema by its exact schema_id."""
        return self._schemas_by_id.get(schema_id)

    def get_default_for_class(self, doc_class: DocumentClass) -> ExtractionSchema | None:
        """Retrieve default (latest registered) schema for a document class."""
        schemas = self._schemas_by_class.get(doc_class)
        return schemas[-1] if schemas else None

    def list_schemas(self) -> list[ExtractionSchema]:
        """List all registered schemas."""
        return list(self._schemas_by_id.values())


# Global default instance
default_schema_registry = SchemaRegistry()
