"""Architecture boundary tests verifying modular monolith separation of concerns."""

import ast
from pathlib import Path


def get_imported_modules(file_path: Path) -> set[str]:
    """Parse a python file into an AST and extract all top-level imported module names."""
    with open(file_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module.split(".")[0])
    return modules


class TestArchitectureBoundaries:
    """Automated architectural constraint verification."""

    def test_domain_layer_does_not_import_frameworks(self) -> None:
        """Domain models must be pure Python and Pydantic only.

        Forbidden in domain: fastapi, sqlalchemy, alembic, starlette, httpx, and upstream forensic engines.
        """
        domain_dir = Path("src/document_intelligence/domain")
        forbidden = {
            "fastapi",
            "sqlalchemy",
            "alembic",
            "starlette",
            "httpx",
            "cv2",
            "torch",
            "docling",
            "surya",
            "pdfforensics",
            "sherloq",
        }

        for py_file in domain_dir.rglob("*.py"):
            imports = get_imported_modules(py_file)
            violations = imports.intersection(forbidden)
            assert not violations, (
                f"Architecture violation in {py_file}: Domain layer must not import {violations}"
            )

    def test_no_upstream_engines_directly_imported_in_application(self) -> None:
        """Application code must not directly import upstream clone folders or raw libraries.

        Strict adapter boundary: only `modules/forensics/adapters/pdf_structural/adapter.py`
        is permitted to import `pdfforensics`.
        """
        app_dir = Path("src/document_intelligence")
        forbidden = {
            "upstream",
            "pdfforensics",
            "sherloq",
            "docshield",
            "surya",
        }

        for py_file in app_dir.rglob("*.py"):
            normalized_path = str(py_file).replace("\\", "/")
            allowed_engine_imports: set[str] = set()

            # The dedicated PDF structural adapter package is the sole sanctioned bridge to pdfforensics
            if "/modules/forensics/adapters/pdf_structural/" in normalized_path:
                allowed_engine_imports.add("pdfforensics")

            imports = get_imported_modules(py_file)
            violations = imports.intersection(forbidden - allowed_engine_imports)
            assert not violations, (
                f"Direct upstream engine import violation in {py_file}: {violations}"
            )

    def test_all_domain_models_use_uuid_string_ids(self) -> None:
        """All entities must provide string UUID IDs."""
        from document_intelligence.domain.enums import (
            AuditEventType,
            EntityType,
            EvidenceType,
            FindingCategory,
            FindingSeverity,
            FindingStatus,
            ReviewDecisionType,
        )
        from document_intelligence.domain.models import (
            AuditEvent,
            Case,
            Document,
            EvidenceNode,
            ForensicFinding,
            InvestigationDossier,
            ProcessingRun,
            ReviewDecision,
        )

        entities: list[object] = [
            Case(title="Sample"),
            Document(
                case_id="case-1",
                original_filename="sample.pdf",
                media_type="application/pdf",
                file_extension=".pdf",
                file_size_bytes=100,
                sha256="a" * 64,
                storage_key="case-1/sample.pdf",
            ),
            ProcessingRun(
                case_id="case-1",
                document_ids=["doc-1"],
                pipeline_name="test",
                pipeline_version="1.0",
            ),
            EvidenceNode(
                case_id="case-1",
                processing_run_id="run-1",
                evidence_type=EvidenceType.OCR_TEXT,
                title="Token",
                description="desc",
                source_component="test",
                source_version="1.0",
            ),
            ForensicFinding(
                case_id="case-1",
                processing_run_id="run-1",
                category=FindingCategory.OTHER,
                title="Finding",
                description="desc",
                severity=FindingSeverity.INFO,
                source_component="test",
            ),
            InvestigationDossier(
                case_id="case-1",
                executive_summary="Summary",
                created_by="admin",
            ),
            ReviewDecision(
                case_id="case-1",
                finding_id="f-1",
                reviewer_id="rev-1",
                decision=ReviewDecisionType.ACCEPT,
                comment="OK",
                previous_status=FindingStatus.DETECTED,
                new_status=FindingStatus.CONFIRMED_OBSERVATION,
            ),
            AuditEvent(
                case_id="case-1",
                event_type=AuditEventType.CASE_CREATED,
                entity_type=EntityType.CASE,
                entity_id="case-1",
            ),
        ]

        for entity in entities:
            entity_id = entity.id  # type: ignore[attr-defined]
            assert isinstance(entity_id, str)
            assert len(entity_id) == 36
            assert entity_id.count("-") == 4
