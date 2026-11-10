# EVIDEXA Platform Architecture Blueprint: Modular Monolith
**Platform:** EVIDEXA - AI-Powered Digital Forensics & Document Intelligence  
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
│       │       ├── consistency.py       # /api/v1/cases/{case_id}/consistency endpoints
│       │       ├── graph.py             # /api/v1/cases/{case_id}/graph investigation query endpoints
│       │       ├── dossier.py           # /api/v1/cases/{case_id}/dossiers & /findings/aggregated endpoints
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
│       │       ├── consistency.py       # Cross-document consistency findings, comparisons, reviews
│       │       ├── classification.py    # Document & page classification candidates & overrides
│       │       ├── extraction.py        # Extraction schemas, field definitions, candidate values
│       │       ├── entity_resolution.py # Cross-document entity mentions & candidate matches
│       │       ├── relationship.py      # Directed cross-document ontology relationships (V2)
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
│       │   ├── entity_resolution/       # Deterministic entity matching & candidate resolution
│       │   ├── relationship_detection/  # Cross-document graph detectors & ontology engine
│       │   ├── consistency/             # Cross-document consistency engine & deterministic rules
│       │   │   ├── context.py           # ConsistencyContext holding docs, fields, signals
│       │   │   ├── financial.py         # Strict Decimal precision & currency comparison rules
│       │   │   ├── engine.py            # ConsistencyRuleRegistry & ConsistencyAnalysisEngine
│       │   │   ├── rules/               # Rule families (A: invoice/receipt, B: po/invoice, C: bank/inv, D: identity, E: duplicates, F: temporal)
│       │   │   └── service.py           # ConsistencyAnalysisService application coordinator
│       │   ├── graph/                   # Unified Evidence Graph query layer & pathfinding
│       │   │   ├── projector.py         # Deterministic relational projection engine
│       │   │   ├── engine.py            # Graph exploration, neighborhood BFS & cycle-safe pathfinding
│       │   │   └── service.py           # EvidenceGraphService query coordinator
│       │   ├── dossier/                 # Findings aggregation & evidence dossier engine
│       │   │   ├── aggregator.py        # Unified findings compiler across forensic/consistency subsystems
│       │   │   ├── generator.py         # 12-section dossier compiler with SHA-256 canonical hashing
│       │   │   ├── export/              # Deterministic PDF (pikepdf) and JSON artifact exporters
│       │   │   └── service.py           # InvestigationDossierService coordinator
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
│               ├── entity_match_repository.py # Entity match & review persistence
│               ├── relationship_repository.py # Directed relationship persistence
│               ├── consistency_repository.py  # Consistency finding & review persistence
│               ├── dossier_repository.py      # Investigation dossier & review persistence
│               └── audit_repository.py  # Append-only audit & checkpoint repository
│
├── alembic/                             # Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py        # Initial SQLite DDL migration
│       ├── 002_architecture_hardening.py # Checkpoints, link tables, unique constraints
│       ├── 006_relationship_semantics.py # Directed ontology and evidentiary review models
│       ├── 007_cross_document_consistency.py # Cross-document consistency models & review history
│       └── 008_evidence_dossier.py     # Dossier payload, content hash, sections, aggregated reviews
│
├── tests/                               # Comprehensive Automated Test Suite (369 tests)
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
- **Phase 2C.3.3 (Cross-Document Consistency Analysis Engine):**
  - Modular Monolith Module `modules/consistency/`: Deterministic cross-document consistency engine evaluating 6 rule families:
    - Family A: Invoice & Receipt (Totals, References, Merchant, Timing)
    - Family B: Purchase Order & Invoice (PO Ref, Parties, Financials/Overrun, Line-Item Quantity & Price)
    - Family C: Invoice & Bank Statement (Settlement match, Ambiguous multiple transactions, Timing)
    - Family D: Supplier & Tax ID Consistency (Tax ID conflicts, unstated tax ID as insufficient evidence)
    - Family E: Duplicate vs Conflicting Records (Byte-identical, semantic duplicates, conflicting invoice number reuse)
    - Family F: Procurement & Payment Lifecycle Temporal Ordering (PO vs Invoice date, due date vs payment)
  - Strict Arbitrary-Precision Financial Arithmetic: `minor_unit_quantization` using Python `Decimal` across all financial comparisons.
  - Non-Verdict Evidentiary Semantics: Every check emits `CONSISTENT`, `INCONSISTENT`, `POTENTIAL_ANOMALY`, `INSUFFICIENT_EVIDENCE`, or `NOT_APPLICABLE`.
  - Relational Persistence & Alembic Migration 007 (`007_cross_document_consistency`): Added `consistency_findings` and `consistency_reviews` tables.
- **Phase 2C.4 (Unified Evidence Graph & Investigation Query Layer):**
  - Modular Monolith Module `modules/graph/`: Framework-neutral in-memory projection over authoritative relational records without persisting a duplicate graph database.
  - Grounded Node & Edge Types: Represents cases, documents, evidence nodes, forensic findings, consistency findings, organizations, persons, invoices, receipts, purchase orders, bank transactions, and accounts.
  - Deterministic Identity Hashing: Stable UUIDv5 node and edge identifiers grounded in case ID, node type, and source entity ID (`deterministic_node_id`, `deterministic_edge_id`).
  - Graph Traversal & Query Engine (`EvidenceGraphEngine`):
    - Bounded graph filtering by node type, relationship type, evidentiary status, and document IDs.
    - Cycle-safe k-hop neighborhood BFS expansion around seed nodes with depth and node limit safeguards.
    - Evidentiary path search between source and target nodes with cycle prevention, max depth bounds, and `confirmed_only` filtering.
    - Sanitized display labels guaranteeing zero unmasked plaintext PII.
- **Phase 2D (Findings Aggregation, Investigator Workflow & Evidence Dossier):**
  - Findings Aggregation Layer (`modules/dossier/service.py`): Deterministic aggregation combining forensic findings (`FindingRepository`) and cross-document consistency findings (`ConsistencyRepository`) into unified `AggregatedFinding` entities.
  - Epistemic Evidentiary Statuses: Strict 4-tier model (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`) with human review override ledger (`AggregatedFindingReview`).
  - 12-Section Investigation Evidence Dossier: Standardized analytical structure compiling Executive Summary, Scope, Document Registry, Forensic Metadata, Optical Analysis, Entity Resolution, Cross-Document Consistency, Evidence Graph, Chronology, and Cryptographic Hash Manifest.
  - Vector PDF & Structured JSON Export: Deterministic, vector PDF rendering (`PdfDossierExporter`) using `pikepdf` with legal non-adjudication disclaimers and JSON data exchange (`JsonDossierExporter`).
  - Relational Persistence & Alembic Migration 008 (`008_evidence_dossier`): Schema migration for `investigation_dossiers` and `aggregated_finding_reviews`.
- **Phase 3A (Investigator Frontend Foundation & Application Shell):**
  - Modern Single-Page Application (SPA) in `frontend/` powered by React 18, TypeScript, Vite, and Tailwind CSS.
  - Strict Brand Identity (`docs/BRAND_GUIDE.md`): Deep Midnight foundation (`#0B132B`), Charcoal containers (`#1C2541`), Slate borders (`#2E3856`), Electric Cyan accent (`#00E5FF`), and accessible status signals.
  - Accessible Evidentiary Semantics: Guaranteed text label + semantic icon pairing across all badges (`StatusBadge`), eliminating color-alone communication.
  - Typed API Client Layer (`src/api/client.ts`): Typed HTTP client with RFC 7807 error envelope extraction, custom `ApiClientError`, query string serializer, and TanStack React Query cache invalidation.
  - Workspace Navigation & Layout Shell: Dynamic sidebar with geometric mark SVG logo, Case Context switcher, active case indicator, and breadcrumb header.
  - Investigation Case Management (`CasesPage`): Case catalog, lifecycle filtering (`ACTIVE`, `UNDER_REVIEW`, `COMPLETED`, `ARCHIVED`, `DRAFT`), search, and case creation modal.
  - Case Overview Dashboard (`CaseOverviewPage`): Authentic metrics grid (documents, findings, consistency runs, relationships, dossiers), recent documents table, priority findings, and dossier generation/export actions.
  - Clean Phase Placeholders (`PlaceholderPage`): Clear module cards for upcoming Phase 3B (Document Inspection), 3C (Interactive Graph Canvas), 3D (Findings Workbench), and 3E (Dossier Workbench).
- **Phase 3B.1 (Document Inventory, Upload & Processing Workspace):**
  - Case-scoped Document Inventory (`DocumentsPage`) with real-time KPI metrics, search, format filtering, multi-criteria sorting, and responsive pagination.
  - Secure Document Upload Modal (`DocumentUploadModal`) with drag-and-drop, 50MB file size ceiling, extension checks, duplicate detection, and examiner attribution.
  - Slide-Over Document Detail Drawer (`DocumentDetailDrawer`) displaying full copyable SHA-256 digests, physical storage keys, runs history, and raw evidence download.
  - Real-Time Processing Controls (`ProcessingControls`) executing backend PDF structural forensics, visual ELA, hybrid OCR, document classification, and structured field extraction with in-flight safeguards.
- **Phase 3B.2 (Visual Document Heatmap & OCR Inspector):**
  - High-performance visual PDF canvas viewer (`PdfDocumentViewer`) powered by `pdfjs-dist` with synchronized zoom (25%–300%), rotation (90° increments), fit-to-width, and reset controls.
  - Canonical Coordinate Transformation Contract (`frontend/src/utils/coordinates.ts`): Rigorous conversion of backend top-left normalized coordinates (`NORMALIZED_0_1`) to display pixels across arbitrary rotations and zoom levels.
  - Interactive OCR Token Overlay & Inspector (`OcrInspector`): Reading-order token/line presentation, real-time search, engine provenance indicators (digital vector text vs OCR), and bidirectional click-to-highlight navigation.
  - Structured Field Extraction Inspector (`StructuredExtractionInspector`): Schema-driven field display with automatic PII / sensitive financial identifier masking (accounts, PAN, tax IDs) and "Locate on Page" coordinate navigation.
  - Forensic Findings & Anomaly Inspector (`FindingsInspector`): Severity distribution filtering, non-verdict forensic caveat banners, and direct supporting evidence provenance links.
  - Visual Error Level Analysis (ELA) Heatmap Raster Overlay: Canvas blend integration and dedicated backend artifact retrieval endpoint (`GET /cases/{case_id}/documents/{document_id}/artifacts/{run_id}/{filename}`).
  - Three-Region Investigation Workspace (`DocumentExaminePage`): Responsive layout combining Page Thumbnail Strip, Canvas Document Viewer, and Multi-tab Inspector with collapsible panels.
- **Phase 3C (Interactive Evidence Graph Canvas):**
  - High-performance interactive graph visualization workspace (`EvidenceGraphPage` at `/cases/:caseId/graph`) powered by `@xyflow/react` and `@dagrejs/dagre`.
  - Hierarchical Directed Layout & Transformers (`frontend/src/components/graph/layout.ts`): Converts backend `GraphNode` and `GraphEdge` payloads into React Flow nodes and edges, laying out connections hierarchically (LR) with Dagre.
  - Custom Typed Graph Nodes (`EvidenceGraphNode`): 16 specialized node configurations covering all domain categories (`CASE`, `DOCUMENT`, `PERSON`, `ORGANIZATION`, `SUPPLIER`, `BUYER`, `MERCHANT`, `BANK`, `ACCOUNT`, `INVOICE`, `RECEIPT`, `PURCHASE_ORDER`, `BANK_TRANSACTION`, `EVIDENCE`, `FORENSIC_FINDING`, `CONSISTENCY_FINDING`) with automated PII masking for sensitive account identifiers, category badges, and page coordinate provenance.
  - Directed Evidentiary Edges (`EvidenceGraphEdge`): Canonical predicate labels with distinct evidentiary status stroke styles (`CONFIRMED` electric cyan, `CANDIDATE` amber dashed, `CONTRADICTED` crimson dashed, `UNRESOLVED` slate dotted, `REJECTED` muted strike-through).
  - Investigation Controls Bar (`GraphControlsBar`): Fast debounced text search with autocomplete drop-down, node type multi-filters, relationship status toggles, smooth fit-view, and Dagre re-layout triggers.
  - Deep Details Inspector Sidebar (`GraphDetailsInspector`): Multi-panel drawer for selected node display attributes and evidentiary provenance; inspects edge predicates, relationship status, heuristic scores, explanations, and supporting evidence references; provides 1-click cross-workspace navigation to visual document examination (`/cases/:caseId/documents/:documentId/examine`).
  - Bounded Pathfinding Modal (`PathExplorationPanel`): Interactive path search between arbitrary source and target nodes with depth selectors (1–6 hops), confirmed-only filtering, and canvas path highlight synchronization.
  - Dynamic Neighborhood Expansion: In-situ 2-hop BFS expansion leveraging backend `GET /cases/{case_id}/graph/nodes/{node_id}/neighbors` without reloading entire case projection.
- **Phase 3D (Unified Findings & Investigator Review Workbench):**
  - Dedicated Investigation Route (`FindingsWorkbenchPage` at `/cases/:caseId/findings`): Unified findings review workspace removing placeholder badges and providing integrated case findings triage.
  - Epistemic Classification Preservation (`EpistemicNoticeBanner`, `Badge`): Contextual legal disclaimer preventing premature conclusions; visual distinctions and expandable guidelines for `OBSERVED_FACT` (cyan), `AUTOMATED_INDICATOR` (amber), `ANALYTICAL_INTERPRETATION` (purple), and `INVESTIGATOR_CONCLUSION` (emerald).
  - Findings Inventory & Filter Toolbar (`FindingsFilterToolbar`, `FindingsTable`): Multi-facet filtering by epistemic classification, severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`), review status (`UNREVIEWED`, `CONFIRMED_OBSERVATION`, `DISMISSED_FALSE_POSITIVE`, `MARK_INCONCLUSIVE`, `REQUEST_MORE_EVIDENCE`, `MARK_NEEDS_REVIEW`), and subsystem source; search by title, description, rule, or finding ID.
  - Deep Findings Inspection (`FindingDetailPanel`): Forensic explanation breakdown, heuristic confidence score notice (clarifying relative algorithmic ranking weight vs. non-probabilistic fraud indicators), known limitations & caveats, and direct deep-links to document examination page coordinates (`/cases/:caseId/documents/:documentId/examine?page=:pageNum`).
  - Human Review Adjudication Workflow (`FindingReviewModal`): Modal form supporting 5 review actions (`CONFIRM_OBSERVATION`, `DISMISS_FALSE_POSITIVE`, `MARK_INCONCLUSIVE`, `REQUEST_MORE_EVIDENCE`, `MARK_NEEDS_REVIEW`), mandatory rationale textarea, asserted examiner identifier, explicit confirmation acknowledgment, and double-submission protection.
  - Append-Only Review Ledger: Chronological review history displayed on each finding; backend audit logs (`REVIEW_DECISION_RECORDED`) preserve all review transitions without destructive mutations.
  - Case Dossier Readiness & Sealing Drawer (`DossierReadinessDrawer`): Real-time review-readiness metrics (total, reviewed, unreviewed, inconclusive, contradictory); new 12-section dossier draft generation (`POST /cases/{case_id}/dossiers/generate`); snapshot finalization (`POST /cases/{case_id}/dossiers/{id}/finalize`) freezing approved dossier state and recording canonical SHA-256 hash; vector PDF and structured JSON downloads.
- **Phase 3E (End-to-End Investigation Integration & Reliability):**
  - Complete case lifecycle validation and hardening connecting document ingestion, PDF structural forensics, visual ELA, hybrid OCR, entity resolution, relationship detection, consistency analysis, unified evidence graph, findings workbench, human reviews, and sealed dossier generation.
  - End-to-end integration test harness (`tests/integration/test_phase_3e_investigation_lifecycle.py`) validating multi-document forensic audit pipelines with zero fabricated data.
- **Phase 4A (Grounded AI Investigation Assistant):**
  - Modular Monolith Module `modules/assistant/`: Controlled, evidence-grounded AI assistant operating strictly on authoritative case records.
  - Grounded Evidence Retrieval (`CaseEvidenceRetriever`): Read-only, bounded multi-subsystem evidence compiler operating strictly within the target `case_id`. Compiles documents, forensic findings, consistency findings, entities, relationships, evidence nodes, and investigator reviews with automatic PII masking. Cross-case access strictly prohibited (HTTP 404).
  - Multi-Layered Prompt Injection & Untrusted Data Boundary: Document and extracted text treated strictly as untrusted data encapsulated within `<case_evidence>` XML tags. System instructions forbid executing embedded commands, overriding instructions, or producing legal verdicts.
  - Pluggable LLM Provider Abstraction (`LlmProviderProtocol`): Decoupled provider interface supporting deterministic offline testing via `MockLlmProvider` and external OpenAI/Ollama compatible endpoints via `HttpLlmProvider` with strict timeout and fallback handling.
  - Strict Epistemic Separation & Citation Verification: Response schema categorizes outputs into Observed Facts, Automated Indicators, Analytical Interpretations, Contradictory Evidence, Unresolved Questions, and Limitations. All citations (`[E-1]`, `[E-2]`) are verified against real retrieved entities and findings; ungrounded IDs are purged automatically, and valid citations receive deep links to document examination and findings triage.
  - Dedicated Investigator Frontend (`AssistantPage` at `/cases/:caseId/assistant`): Interactive chat interface with 6 question category chips, collapsible epistemic breakdown accordions, clickable citation cards, follow-up query suggestions, and prominent evidentiary boundary notices.
- **Phase 4B (AI Reliability, Grounding & Adversarial Evaluation):**
  - Deterministic Claim-Level Grounding Engine (`ClaimGroundingValidator` in `modules/assistant/grounding.py`): Re-evaluates all generated citations against authoritative case context verifying case isolation, subsystem consistency, spatial/page matching, and token-level lexical overlap (>= 25% overlap ratio). Prunes ungrounded citations deterministically without secondary LLM calls.
  - Contradiction Omission Detection: Calculates omission ratios when retrieved case context contains explicit contradictions (`INCONSISTENT`, `POTENTIAL_ANOMALY`, `CONTRADICTED`) and injects automatic limitation alerts if the generated answer suppresses them.
  - Repeatable Synthetic Evaluation Harness (`AssistantReliabilityEvaluator` in `modules/assistant/evaluator.py`): Headless benchmark engine evaluating 10 version-controlled scenarios in `tests/fixtures/eval/benchmark_scenarios.py` across 7 quantitative reliability metrics: citation resolution rate, claim support rate, unsupported claim rate, contradiction omission rate, insufficient evidence accuracy, prompt injection resistance rate, and cross-case isolation violations (target: 0.0).
  - PII Sanitization Pipeline (`sanitization.py`): Systematic masking and token redaction for PANs, Aadhaar, SSNs, EINs, credit card numbers, and raw/spaced/dashed financial account numbers across retrieved documents, OCR snippets, conversation history, and user queries before prompt assembly.
  - Hardened Provider Resilience & Error Hierarchy: `HttpLlmProvider` guarded with 256KB request and 512KB response payload caps, connection/read timeouts, exponential backoff retries, and typed exception discrimination (`ProviderConnectionError`, `ProviderTimeoutError`, `ProviderRateLimitError`, `ProviderPayloadLimitError`, `ProviderResponseError`).
  - Frontend Transparency: Distinct provider failure alert banners with retry buttons, insufficient evidence warning notices, grounded citation badges, and epistemic classification accordions.
- **Phase 4B.1 (Independent Evaluation Integrity & Safety Closure):**
  - Claim-Level Grounding vs. Relevance Separation: Explicit mathematical separation between citation resolution (record exists & case isolation holds), citation lexical relevance (token overlap heuristic), and semantic claim support. Introduced `ClaimSupportStatus` enum (`SUPPORTED`, `CONTRADICTED`, `UNVERIFIED`) and `ClaimVerificationReport`.
  - Deterministic Reversal & Semantic Inversion Detection: Deterministic rule-based checks detecting numerical mismatches/discrepancies, payment status reversals (paid vs unpaid/overdue), unauthorized promotion of candidate relationships to confirmed partnerships/subsidiaries, and document attribution flips.
  - Independent Benchmark Negative Controls: Suite of 7 independent negative controls (`tests/unit/test_assistant_benchmark_negative_controls.py`) verifying that inverted claims, incorrect amounts, and unsupported legal conclusions are caught with zero reliance on synthetic test leniency.
  - Reasoning Manipulation Defense: Defends against adversarial prompt injection targeting investigative logic (suppressing contradiction findings, upgrading automated indicators to conclusions, promoting candidate relationships, or ignoring incriminating records) across OCR text, context, entity names, and finding descriptions.
  - PII False-Positive Prevention & Evidence Utility Preservation: Protected regex stashing for legitimate evidence identifiers (invoices, purchase orders, transactions, case refs) and dates, preventing destruction of critical evidentiary codes during account and tax ID masking.
  - Bounded Streaming Provider Architecture: Hardened `HttpLlmProvider` utilizing chunk-level streaming (`client.stream`) with early `Content-Length` checks and byte accumulation ceilings (512KB) preventing out-of-memory exhaustion, honoring upstream `Retry-After` headers on 429/503, failing fast on non-retryable 4xx errors, and sanitizing credentials from error messages.
  - Frontend Investigator Transparency: Replaced misleading "Grounded" badge with precise "Citations Linked ({count})" and "Insufficient Evidence" status indicators with explicit investigator guidance notes.
- **Phase 4C+ (Future Multi-Agent & Orchestration Milestones):** Specialized cross-case analytical graphs, fraud ring detection, and multilingual document intelligence models.

