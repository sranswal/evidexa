"""Detector exports for cross-document relationship discovery."""

from document_intelligence.modules.relationship_detection.detectors.bank_statement import (
    BankStatementRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.base import (
    BaseRelationshipDetector,
    DetectionContext,
)
from document_intelligence.modules.relationship_detection.detectors.document_similarity import (
    DocumentRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.entity_role import (
    EntityRoleRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.invoice import (
    InvoiceRelationshipDetector,
)
from document_intelligence.modules.relationship_detection.detectors.receipt import (
    ReceiptRelationshipDetector,
)

__all__ = [
    "BaseRelationshipDetector",
    "DetectionContext",
    "InvoiceRelationshipDetector",
    "ReceiptRelationshipDetector",
    "BankStatementRelationshipDetector",
    "EntityRoleRelationshipDetector",
    "DocumentRelationshipDetector",
]
