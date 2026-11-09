# EVIDEXA Platform Architecture Blueprint: Modular Monolith
**Platform:** EVIDEXA — AI-Powered Digital Forensics & Document Intelligence  
**System:** Modular Monolith Clean Architecture  
**Status:** Approved & Implemented  
**Date:** November 2026

---

## 1. Architectural Style & Philosophy

The platform is designed as a **Modular Monolith** using Clean Architecture and Domain-Driven Design (DDD) principles.

### Why Modular Monolith?
1. **Low Cognitive & Operational Complexity:** Avoids premature distributed systems pitfalls (network latency, distributed transaction rollbacks, split-brain consensus, orchestration overhead) while preserving strict code boundaries.
2. **Single Process, Strong Boundaries:** Modules communicate through well-defined internal interfaces, application services, and domain contracts.
3. **Independent Extensibility:** Each forensic capability (PDF structural analysis, visual ELA/copy-move, OCR layout, fraud-ring clustering, agentic reasoning) can be built in its own module without rewriting or mutating the core platform.
4. **Future Microservices Extraction Ready:** Should specific modules (such as heavy deep-learning inference) require independent horizontal scaling in future phases, the module boundaries and contracts already mirror service boundaries.

---

## 2. Layered Structure & Dependency Direction

The architecture enforces a strict **unidirectional dependency flow** from external delivery mechanisms toward the central domain model:

```
[ API Layer (FastAPI Routes, Request/Response DTOs, Exception Handlers) ]
                                 │
                                 ▼
[ Application Layer (Modules & Services: CaseService, DocumentService, AuditLedger) ]
                                 │
                                 ▼
[ Domain Layer (Entities: Case, Document, EvidenceNode, ForensicFinding, Enums) ]
                                 ▲
                                 │
[ Infrastructure Layer (Repositories, SQLite/SQLAlchemy 2.0, Filesystem Storage, Adapters) ]
```

### Architectural Dependency Invariants
1. **Domain Isolation:** The `domain` layer has zero dependencies on frameworks (`fastapi`, `sqlalchemy`, `alembic`, `starlette`) or third-party engines. It depends exclusively on pure Python and Pydantic v2.
2. **Transport Agnostic:** Application services do not take `Request`, `UploadFile`, or HTTP headers. They accept pure Python streams, primitives, and domain objects.
3. **Persistence Inversion:** Domain entities are independent of database tables. Persistence models (`models.py`) map to domain entities inside repository implementations (`repositories/`).
4. **Upstream Isolation:** No module in `src/document_intelligence` directly imports from the cloned `upstream` directories. Upstream engines will only be integrated in future phases through specialized adapters.

---

## 3. Directory & Module Breakdown

```
document-intelligence-platform/
├── src/
│   └── document_intelligence/
│       ├── __init__.py                  # Root package metadata
│       ├── main.py                      # FastAPI application factory, lifespan, and middleware
│       │
│       ├── api/                         # HTTP Transport Layer
│       │   ├── dependencies.py          # Dependency injection providers (db, storage, services)
│       │   ├── error_handlers.py        # Centralized RFC-style JSON error handlers
│       │   └── routes/                  # Versioned route controllers (/api/v1)
│       │       ├── health.py            # /health & /api/v1/health endpoints
│       │       ├── cases.py             # /api/v1/cases endpoints
│       │       ├── documents.py         # /api/v1/cases/{case_id}/documents upload & list
│       │       ├── findings.py          # /api/v1/cases/{case_id}/findings query
│       │       ├── ocr.py               # /api/v1/cases/{case_id}/documents/{document_id}/ocr endpoints
│       │       ├── understanding.py     # /api/v1/cases/{case_id}/documents/{document_id}/classification & extraction
│       │       └── audit.py             # /api/v1/cases/{case_id}/audit-events & /verify
│       │
│       ├── core/                        # Core Cross-Cutting Foundation
│       │   ├── config.py                # Pydantic Settings (ENV, paths, upload limits)
│       │   ├── exceptions.py            # Domain & platform exception hierarchy
│       │   ├── logging.py               # Structured logger with PII & content masking
│       │   └── security.py              # Magic byte inspection, safe paths, SHA-256
│       │
│       ├── domain/                      # Domain Model Layer (Pure Business Rules)
│       │   ├── enums.py                 # StrEnum lifecycles (DocumentClass, FieldDataType, FieldValidationStatus...)
│       │   ├── identifiers.py           # UUID4 generator, CASE-YYYYMMDD-XXXX, UTC time
│       │   └── models/                  # Core Pydantic domain models
│       │       ├── case.py              # Case aggregate root with lifecycle transitions
│       │       ├── document.py          # Document entity with SHA-256 & storage key
│       │       ├── processing_run.py    # Pipeline execution tracking
│       │       ├── evidence_node.py     # Atomic evidence tokens & bounding boxes
│       │       ├── forensic_finding.py  # Anomaly interpretations citing evidence
│       │       ├── classification.py    # Document & page classification candidates & overrides
│       │       ├── extraction.py        # Extraction schemas, field definitions, candidate values
│       │       ├── ocr.py               # ExtractedDocumentText, tokens, lines, tables
│       │       ├── investigation_dossier.py # Versioned, auditable report dossiers
│       │       ├── review_decision.py   # Human investigator review records
│       │       ├── audit_event.py       # Cryptographic ledger blocks & AuditCheckpoint
│       │       └── bounding_box.py      # Canonical PageGeometry & BoundingBox
│       │
│       ├── modules/                     # Application Service Orchestration
│       │   ├── cases/service.py         # Case creation, retrieval, and status workflows
│       │   ├── documents/service.py     # Safe document ingestion & duplicate detection
│       │   ├── forensics/               # Forensic adapters (PDF structural, ELA, copy-move)
│       │   ├── ocr/                     # PDFium, RapidOCR, Hybrid routing adapters
│       │   ├── understanding/           # Document classification & structured field extraction
│       │   │   ├── classification/      # RuleBasedDocumentClassifier & compiled regex patterns
│       │   │   ├── extraction/          # StructuredFieldExtractor & validators
│       │   │   │   ├── schemas/         # Invoice, Receipt, Bank Statement schemas & registry
│       │   │   │   └── validators.py    # Normalizers (date, currency, decimal), masking & arithmetic
│       │   │   └── service.py           # DocumentUnderstandingService application coordinator
│       │   └── audit/ledger.py          # Append-only hash chain, checkpointing & lock service
│       │
│       └── infrastructure/              # Infrastructure & Adapters
│           ├── persistence/
│           │   ├── database.py          # SQLAlchemy 2.0 engine, WAL mode & FK pragma
│           │   └── models.py            # SQLAlchemy ORM table definitions & link tables
│           ├── storage/
│           │   ├── interface.py         # DocumentStorageProtocol interface
│           │   └── filesystem.py        # Atomic filesystem storage with read-only flag
│           └── repositories/
│               ├── case_repository.py   # Case persistence repository
│               ├── document_repository.py # Document persistence repository
│               ├── finding_repository.py  # Finding persistence repository
│               └── audit_repository.py  # Append-only audit & checkpoint repository
│
├── alembic/                             # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py        # Initial SQLite DDL migration
│       └── 002_architecture_hardening.py # Checkpoints, link tables, unique constraints
│
├── tests/                               # Comprehensive Automated Test Suite (59 tests)
│   ├── conftest.py                      # Isolated test database and client fixtures
│   ├── architecture/
│   │   └── test_architecture_boundaries.py # AST-based layer isolation checks
│   ├── integration/
│   │   ├── test_api.py                  # End-to-end API route tests
│   │   ├── test_database_integrity.py   # FK cascades, unique constraints, link tables
│   │   ├── test_storage.py              # Storage, traversal, and size limit tests
│   │   └── test_storage_hardening.py    # Overwrite protection, Windows device names, read-only
│   └── unit/
│       ├── test_domain_models.py        # Domain invariants, validations, transitions
│       ├── test_coordinates.py          # PageGeometry, corners, zero-area, rotation, PDF points
│       ├── test_audit_chain.py          # Hash chaining, tampering, & deletion tests
│       └── test_audit_chain_hardening.py # Checkpoint tail deletion detection & concurrency
│
├── data/                                # Local runtime data directory (Git ignored)
│   ├── app.db                           # SQLite database
│   ├── originals/                       # Immutable uploaded documents
│   ├── artifacts/                       # Generated heatmaps, previews, and exports
│   └── temp/                            # Temporary upload staging
│
├── research/                            # Prioritized upstream research deliverables
├── upstream/                            # Cloned open-source reference implementations
├── pyproject.toml                       # Build system, pinned dependencies, tool configs
└── README.md                            # Main project overview and run guide
```

---

## 4. Primary Data Flows

### Ingestion Flow
1. User issues `POST /api/v1/cases/{case_id}/documents` with a binary file stream.
2. `DocumentService` validates case existence.
3. `security.validate_file_signature` inspects initial 16 magic bytes to ensure file content matches declared media type (PDF, PNG, JPEG, TIFF).
4. `FilesystemDocumentStorage` writes stream into `data/temp/tmp_{uuid}.upload`, continuously computing SHA-256 and enforcing the 50 MB size limit.
5. Upon successful completion, the temporary file is atomically moved to `data/originals/{case_id}/{document_id}.ext`.
6. `DocumentService` checks if the SHA-256 already exists in the case. If a duplicate is found, it notes `duplicate_of_document_id` in metadata without discarding.
7. `DocumentRepository` commits metadata to SQLite. If database persistence fails, compensation cleanup removes the stored original file.
8. `AuditLedgerService` appends `DOCUMENT_INGESTED` and `FILE_HASH_REGISTERED` events to the hash chain.

---

## 5. Extension Points for Future Phases

The foundation provides clean extension points:
- **Phase 2B (Forensic Adapters):** Forensic adapters implemented under `ForensicAnalyzer` protocol (PDF structural analysis via `pdf-forensics-kit`, Error Level Analysis via Pillow/OpenCV, and Copy-Move detection via OpenCV ORB).
- **Phase 2C (OCR & Document Understanding):** OCR adapter framework implemented:
  - `PdfiumOcrAdapter` (`pdfium-ocr-engine`) providing programmatic digital character recovery, layout region classification, and tabular grid detection.
  - `RapidOcrAdapter` (`rapidocr-optical-engine`) providing lightweight, CPU-efficient optical character recognition on scanned document pages and images via ONNX Runtime.
  - `HybridOcrAdapter` (`hybrid-ocr-pipeline`) coordinating intelligent page-level routing: programmatic extraction on native digital pages, automatic optical fallback on scanned or sparse pages (configurable threshold), forced OCR support, and alternative extraction provenance preservation.
  - Phase 2C.1.2 Hardening: Pinned reproducible ONNX dependencies, bounded CPU execution controls (`intra_op_num_threads`, `inter_op_num_threads`), resilient partial page failure isolation (`PARTIALLY_SUCCEEDED`), and explicit uncalibrated confidence metadata provenance (`confidence_calibration_method = 'uncalibrated_model_score'`).
- **Phase 2C.2 & 2C.2.1 (Document Classification, Structured Field Extraction & Integrity Hardening):**
  - `RuleBasedDocumentClassifier`: Deterministic, explainable multi-class document & page classification across 7 document classes (`INVOICE`, `RECEIPT`, `BANK_STATEMENT`, `IDENTITY_DOCUMENT`, `TAX_DOCUMENT`, `CONTRACT`, `UNKNOWN`). Produces candidate rankings and matched pattern signals with transparent `rule_ranking_score`. Supports multi-page page-level classification and explainable aggregation.
  - Reviewer Classification Override & Tamper-Evident Audit: Preserves original machine prediction in `predicted_class` while applying `effective_class` and logging full justification to the local append-only cryptographic hash-chained audit ledger. Reviewer identity `overridden_by` represents an asserted reviewer identifier in unauthenticated development mode.
  - `StructuredFieldExtractor`: Explicit schema-driven field extraction engine with candidate ranking, multi-candidate fallback, date normalization (ISO 8601), currency normalization (ISO 4217), decimal normalization, and exact arithmetic validation (`subtotal + tax == total`).
  - Financial Precision (Python `Decimal`): Strictly avoids IEEE 754 binary `float` for monetary amounts. Operates end-to-end with Python `Decimal`, explicit currency minor units (e.g. 0 for JPY, 3 for KWD, 2 for USD/EUR), documented default rounding tolerance (0.05), and string-safe JSON serialization. Discrepancies are surfaced as evidentiary validation warnings, not fraud conclusions.
  - Strict PII Sanitization Across All Persistence Tiers: Account numbers and sensitive string fields are masked (`****{last4}` for $\ge 4$ characters, `****` for $<4$) immediately upon regex match. Unmasked plaintext account numbers are strictly purged from `CandidateValue.raw_text`, `ExtractedFieldValue.raw_text`, `EvidenceNode.raw_value`, extraction JSON artifacts, database rows, and logs.
  - Ambiguity Disambiguation: Ambiguous numeric dates (e.g. `03/04/2024`) and ambiguous currency symbols (`$`, `¥`) require explicit document context (e.g. "USD", "CAD", "en-US", "Tokyo"); without resolving context, values are preserved as `None` with candidate interpretations and explicit validation warnings.
  - Mixed-Document Architecture Reality: Aggregates page-level classifications into a single predominant document class. Extraction runs against a single explicit or inferred schema; heterogeneous multi-schema extraction across mixed pages is supported via targeted page extraction (`options={"page_number": N}`) and queued for Phase 3 orchestration.
  - Complete Evidence Graph Provenance & Artifact Integrity: Every extracted field links to an `EvidenceNode` (`EXTRACTED_FIELD`) referencing source page number, exact normalized bounding boxes (`NORMALIZED_0_1`), supporting OCR token IDs, schema version, and validation status. Artifacts are persisted with SHA-256 integrity verification upon reload; reruns are strictly isolated in separate `ProcessingRun` records without overwriting.
- **Phase 2C.3.1 (Cross-Document Entity Resolution Foundation):**
  - Modular Monolith Module `modules/entity_resolution/`: Deterministic cross-document identity resolution operating strictly within a single case.
  - Initial Entity Types: `ORGANIZATION`, `PERSON`, `TAX_IDENTIFIER`, `INVOICE_REFERENCE`, `BANK_ACCOUNT_REFERENCE`, `CURRENCY_AMOUNT`, `TRANSACTION_REFERENCE`.
  - Core Principle: "Similarity is not identity." Candidate matches never silently convert into confirmed real-world identities.
  - Deterministic Normalization: Unicode NFKC, case folding, conservative punctuation stripping, legal suffix extraction as a separate comparison signal (`LEGAL_SUFFIX_MAP`), leading-zero preservation on references, strict privacy masking (`****{last4}`) on account numbers, and exact `Decimal` minor-unit monetary keys (`USD:1250.00`).
  - Conservative Matching & Contradiction Detection: Exact identifier/reference matching, token and character name similarity, masked account collision disclaimers (`WEAK_AMBIGUOUS`, score $\le 0.40$), amount coincidence disclaimers, and strict contradiction detection (conflicting tax IDs or mismatched currencies suppress matches).
  - Bounded Execution & Blocking: Deterministic blocking keys index mentions to avoid $O(N^2)$ comparisons with configurable comparison limits (`max_comparisons = 5000`).
  - Relational Persistence & Alembic Migration 004: Relational persistence for `entity_candidate_matches` and `entity_match_reviews` allowing multi-criteria filtering, pagination, and durable human review audit trails alongside SHA-256 verified full execution artifacts (`entity_resolution_{run_id}.json`).
  - Human Review Decisions: Supports `CONFIRM_MATCH`, `REJECT_MATCH`, `MARK_AMBIGUOUS` with reviewer history preservation and hash-chained audit ledger events (`ENTITIES_RESOLVED`, `ENTITY_MATCH_REVIEWED`).
- **Phase 2C.3.2 & 2C.3.2.1 (Cross-Document Relationship Engine & Evidentiary Semantics Hardening):**
  - Modular Monolith Module `modules/relationship_detection/`: Deterministic, evidence-backed relationship detection connecting documents, resolved entities, extracted fields, and financial records within a single case.
  - Ontology Version 2.0 (Directed Subject-Predicate-Object Semantics):
    - `Supplier --ISSUED--> Invoice`: Explicit issuer identified on invoice.
    - `Invoice --BILLED_TO--> Buyer`: Explicit recipient/buyer billed on invoice.
    - `Merchant --ISSUED--> Receipt`: Explicit merchant identified on receipt.
    - `Bank --ISSUED--> Bank statement`: Financial institution issuing statement.
    - `Invoice --REFERENCES_PURCHASE_ORDER--> Purchase order`: Explicit PO cross-reference.
    - `Receipt --REFERENCES_INVOICE--> Invoice`: Explicit invoice cross-reference on receipt.
    - `Receipt --RECORDS_PAYMENT--> Payment record`: Explicit authorization/terminal approval code.
    - `Bank statement --CONTAINS_TRANSACTION--> Transaction`: Ledger transaction lines (never fabricated for summary-only schemas).
    - `Transaction --MAY_SETTLE--> Invoice`: Explicit invoice citation $\rightarrow$ `CANDIDATE` ($0.90$); amount/date coincidence $\rightarrow$ `UNRESOLVED` ($0.35$); currency conflict $\rightarrow$ `CONTRADICTED` ($0.0$).
    - `Account --HELD_BY--> Account holder`: Account ownership with masked identifier (`****{last4}`).
    - `Person --REPRESENTS--> Organization`: Explicit corporate representation clause (e.g. Director/CEO of). Mere co-occurrence remains `UNRESOLVED` ($0.25$).
    - `Document --DUPLICATE_OF--> Document`: Byte-identical document content established via SHA-256 digest equality (`DuplicateKind.BYTE_IDENTICAL`). Visual or semantic similarity without byte equality is preserved as `CANDIDATE` (`UNRESOLVED_DUPLICATE_CANDIDATE`).
    - `Document --AMENDS_DOCUMENT--> Document`: Explicit amendment or supersession reference.
    - `Document --SUPPORTS_DOCUMENT--> Document`: Explicit exhibit, schedule, or annexure attachment.
    - `Supplier --INVOICED--> Buyer`: Specific commercial billing event established by invoice co-occurrence.
    - `Supplier --SUPPLIES--> Buyer`: **Strictly reserved** for explicit contractual supply agreements (e.g. Master Supply Agreement); never inferred from invoice co-occurrence.
  - Core Evidentiary Principles & Rigorous Safeguards:
    - Status & Score Separation: `status` is determined strictly by evidentiary rules and review decisions (`StatusDeterminationMethod.EVIDENTIARY_RULE` vs `HUMAN_REVIEW`). `score` reflects heuristic ranking only; scores cannot independently confirm relationships.
    - Accurate Cryptographic Digest Terminology: Renamed to `DOCUMENT_HASH_EQUALITY`; removed misleading references to "cryptographic hash collisions" for equal digests.
    - Human Review & Contradiction Provenance: Confirmation records full reviewer provenance (`reviewer_id`, `reason`, `reviewed_at`); contradictory evidence signals remain completely visible even when an investigator confirms an edge.
    - Contradiction Precedence: Conflicting tax IDs or currency mismatches immediately force status to `CONTRADICTED` and score to $0.0$.
    - Non-Fabrication of Transactions: Summary-only schemas (`bank_statement_v1`) never hallucinate transaction nodes.
    - Coincidence Disclaimers: Amount and date coincidence alone never establishes payment settlement (`UNRESOLVED`, score $0.35$).
    - Zero Plaintext PII Persistence: Sensitive account numbers strictly masked (`****{last4}`).
    - Single-Case Isolation: Cross-case access returns HTTP 404 (`SecurityException`); archived cases reject detection and review with HTTP 422 (`CaseArchivedException`).
  - Relational Persistence & Alembic Migration 006 (`006_relationship_semantics`):
    - Added `ontology_version`, `legacy_relationship_type`, `status_determination_method`, and `duplicate_kind` to `detected_relationships`.
    - Safe data migration for historical V1 records, mapping legacy `ISSUED_BY`, `ISSUED_TO`, `ACCOUNT_HELD_BY`, and demoting co-occurrence `SUPPLIES` to `INVOICED` while preserving original legacy types and complete review history.
- **Phase 3 (Agentic Investigation):** `langgraph` will orchestrate multi-step investigation graphs querying `CaseRepository` and `FindingRepository`.
- **Phase 4 (Reporting):** Dossier generator will assemble `InvestigationDossier` instances and export verified PDF/HTML dossiers.

