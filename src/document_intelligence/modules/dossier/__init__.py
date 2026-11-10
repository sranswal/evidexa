"""Investigation dossier and findings aggregation module."""

from document_intelligence.modules.dossier.aggregator import FindingsAggregator
from document_intelligence.modules.dossier.export.json_exporter import JsonDossierExporter
from document_intelligence.modules.dossier.export.pdf_exporter import PdfDossierExporter
from document_intelligence.modules.dossier.generator import (
    DossierGenerator,
    compute_canonical_content_hash,
)
from document_intelligence.modules.dossier.service import InvestigationDossierService

__all__ = [
    "DossierGenerator",
    "FindingsAggregator",
    "InvestigationDossierService",
    "JsonDossierExporter",
    "PdfDossierExporter",
    "compute_canonical_content_hash",
]
