# EVIDEXA Engineering Development Status

**Intelligence Behind Every Evidence.**  
*Last Updated: November 2026 | Release Target: v0.1.0 (Pre-Release)*

---

## 1. Quality & Verification Metrics

Every commit and capability in EVIDEXA must pass strict static typing, linting, formatting, and automated regression verification gates before integration.

| Verification Gate | Specification / Target | Current Metric | Status |
|---|---|---|:---:|
| **Automated Test Suite (Backend)** | 100% pass rate across unit, integration, and architecture suites | **436 passed**, 89 warnings | **PASS** |
| **Automated Test Suite (Frontend)** | Component and client unit tests (Vitest + Testing Library) | **89 passed**, 0 failures (23 test files) | **PASS** |
| **Frontend Production Build** | Production bundle check (`tsc && vite build`) | **Zero errors**, clean production asset bundle | **PASS** |
| **Linting (Ruff)** | Strict code quality rules (E, W, F, I, B, C4, UP) | **0 errors, 0 warnings** across 218 files | **PASS** |
| **Formatting (Ruff)** | Standardized PEP 8 formatting with 100 char line limit | **218 files cleanly formatted** | **PASS** |
| **Static Type Checking (MyPy)** | Strict type checking with `disallow_untyped_defs = true` | **Success: 0 issues across 151 source files** | **PASS** |
| **Database Migrations (Alembic)** | Verified upgrade and downgrade paths for relational tables | **Head: `008_evidence_dossier`** | **PASS** |
| **Runtime Architecture** | Python 3.12 backend, React 18 + Vite frontend, CPU-optimized | **Verified on Windows 11 / Python 3.12.10 / Node 24** | **PASS** |

---

## 2. Implemented & Operational Subsystems

The backend platform is fully operational via the FastAPI REST API and Python programmatic interface:

1. **Case Management Service:** Full CRUD, soft archival (`CaseStatus.ARCHIVED`), single-case isolation with 404 security barriers.
2. **Document Ingestion Engine:** MIME verification, magic-byte checks, SHA-256 calculation, and isolated master storage.
3. **Forensic Analysis Pipeline:**
   - Subprocess-isolated PDF structural analysis worker (`worker.py`) with 30s timeout and I/O caps.
   - Ephemeral snapshot lifecycle with double SHA-256 integrity verification.
   - Error Level Analysis (ELA) and 2D-DCT copy-move forgery detection.
4. **Document Understanding Layer:**
   - Hybrid adaptive OCR routing (PDFium vector text vs. RapidOCR ONNX optical recognition).
   - Normalized top-left coordinate system (`NORMALIZED_0_1`).
   - Schema-driven field extraction for invoices, receipts, purchase orders, and bank statements.
   - Financial decimal precision (minor unit quantization) and automatic PII masking.
5. **Cross-Document Intelligence Engine:**
   - Deterministic entity resolution across 7 entity types.
   - Relationship Ontology V2: directed Subject-Predicate-Object semantics.
   - Separation of discrete invoice billing events (`INVOICED`) from supply contracts (`SUPPLIES`).
   - Separation of formal status from heuristic ranking scores.
   - Contradiction persistence under human review.
6. **Cross-Document Consistency Analysis Engine:**
   - Deterministic rule engine evaluating 6 rule families (invoice/receipt, PO/invoice, bank statement/invoice, supplier identity/tax ID, duplicate/conflicting records, temporal ordering).
   - Strict `Decimal` monetary precision end-to-end; currency mismatches reported as distinct contradictions.
   - Non-verdict evidentiary semantics (`CONSISTENT`, `INCONSISTENT`, `POTENTIAL_ANOMALY`, `INSUFFICIENT_EVIDENCE`).
   - Human review override lifecycle (`ConsistencyReviewAction`) with persistent audit trails.
7. **Unified Evidence Graph Query Layer:**
   - In-memory projection of heterogeneous evidence records (cases, documents, evidence nodes, forensic findings, consistency findings, relationships, entity candidate matches) without second DB persistence.
   - Directed Subject-Predicate-Object semantics preserving explicit evidentiary statuses (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`, `REJECTED`).
   - Deterministic UUIDv5 node and edge IDs grounded in case and source records.
   - Cycle-safe bounded k-hop neighborhood BFS expansion and multi-hop evidentiary path search.
   - PII masking on financial identifiers and account numbers in display labels.
8. **Findings Aggregation & Evidence Dossier Layer (Phase 2D):**
   - Unified findings aggregator across all forensic and consistency subsystems with 4-level epistemic classification.
   - Append-only investigator review decisions (`AggregatedFindingReview`) asserting human judgment.
   - 12-section formal investigation dossier generator with deterministic SHA-256 canonical content hashing.
   - Reproducible multi-page vector PDF export using existing `pikepdf` dependency (`deterministic_id=True`).
   - Structured JSON dossier export for evidentiary data exchange.
   - Prominent legal non-adjudication disclaimers on every export.
9. **Cryptographic Audit Ledger:**
   - Append-only hash-chained audit trail (`AuditLedgerModel`) with sequence integrity verification.
   - Synchronous SHA-256 artifact verification on storage retrieval.
10. **Investigator Frontend Foundation & Application Shell (Phase 3A):**
   - Modern React 18, TypeScript, Vite, Tailwind CSS application shell in `frontend/`.
   - Strict brand identity implementation adhering to `docs/BRAND_GUIDE.md`: Deep Midnight (`#0B132B`), Dark Charcoal (`#1C2541`), Border Slate (`#2E3856`), and Electric Cyan (`#00E5FF`).
   - Accessible evidentiary status badges (Emerald/Amber/Crimson/Slate) guaranteeing no color-alone status communication.
   - Typed API client with central base URL configuration, RFC 7807 error envelopes, and TanStack React Query cache invalidation.
   - Global investigation workspace navigation shell with layered geometric SVG logo mark, active case badge, and breadcrumbs.
   - Investigation Case Management interface: case catalog, status filtering, and creation modal.
   - Case Overview Dashboard: authentic forensic intelligence metrics (documents, findings, consistency evaluations, detected relationships, dossiers) with explicit uncalculated states.
11. **Document Inventory, Upload & Processing Workspace (Phase 3B.1):**
   - Case-scoped Document Inventory (`DocumentsPage`) with real-time KPI metrics (total files, storage volume, parsed count, identical duplicates).
   - Search by filename, technical document ID, and SHA-256 digest; filtering by document format and ingestion status; multi-criteria sorting.
   - Secure Document Ingestion Modal (`DocumentUploadModal`) with drag-and-drop, client size validation (50 MB cap), extension checks, duplicate detection, and examiner attribution.
   - Document Detail Drawer (`DocumentDetailDrawer`) displaying full cryptographic SHA-256 digests with copy action, storage keys, page count, and duplicate provenance.
   - Interactive Processing Controls (`ProcessingControls`) executing real backend pipelines: PDF Structural Forensics, Visual ELA, Hybrid OCR, Document Classification, and Structured Field Extraction.
   - Dedicated document download endpoint (`GET /cases/{case_id}/documents/{document_id}/download`) and single document detail retrieval (`GET /cases/{case_id}/documents/{document_id}`).
12. **Visual Document Heatmap & OCR Inspector (Phase 3B.2):**
   - Multi-page visual PDF canvas viewer (`pdfjs-dist`) with synchronized zoom (25%–300%), rotation (90° clockwise increments), fit-to-width, and reset controls.
   - Canonical coordinate transformation contract (`NORMALIZED_0_1`) mapping top-left normalized coordinates accurately to canvas layout pixels across zoom and rotation.
   - Interactive OCR token bounding box overlay with hover text inspector, confidence metrics, and bidirectional click-to-highlight navigation.
   - Schema-driven structured field extraction inspector with automatic PII / sensitive financial identifier masking (accounts, PAN, tax IDs) and "Locate on Page" coordinates.
   - Forensic findings and visual anomaly inspector with non-verdict forensic caveat banners, severity distribution filters, and direct evidence provenance links.
   - Visual Error Level Analysis (ELA) heatmap raster overlay with opacity blend and dedicated artifact retrieval endpoint (`GET /cases/{case_id}/documents/{document_id}/artifacts/{run_id}/{filename}`).
   - 3-region workspace (Thumbnail Strip, Document Canvas Viewer, Multi-tab Inspector) with responsive collapsible panels.
13. **Interactive Evidence Graph Canvas (Phase 3C):**
   - Full investigation-grade 3-region canvas (`EvidenceGraphPage` at `/cases/:caseId/graph`) powered by `@xyflow/react` and `@dagrejs/dagre`.
   - 16 custom typed node configurations covering all domain categories (`CASE`, `DOCUMENT`, `PERSON`, `ORGANIZATION`, `SUPPLIER`, `BUYER`, `MERCHANT`, `BANK`, `ACCOUNT`, `INVOICE`, `RECEIPT`, `PURCHASE_ORDER`, `BANK_TRANSACTION`, `EVIDENCE`, `FORENSIC_FINDING`, `CONSISTENCY_FINDING`) with automated PII masking on sensitive account identifiers.
   - Directed Subject-Predicate-Object evidentiary edges with status-aware strokes (`CONFIRMED` cyan, `CANDIDATE` amber dashed, `CONTRADICTED` crimson dashed, `UNRESOLVED` slate dotted, `REJECTED` muted strike-through).
   - Graph Controls Bar with debounced node search, autocomplete dropdown, node-type and status multi-filters, fit-to-view, and Dagre re-layout triggers.
   - Deep Details Inspector for node metadata and edge evidentiary rationale with 1-click cross-workspace navigation to visual document examination (`/cases/:caseId/documents/:documentId/examine`).
   - In-situ 2-hop BFS neighborhood expansion (`GET /cases/{case_id}/graph/nodes/{node_id}/neighbors`) and bounded multi-hop directed pathfinding (`GET /cases/{case_id}/graph/paths`) with canvas path highlights.
14. **Unified Findings & Investigator Review Workbench (Phase 3D):**
   - Case-scoped findings triage workbench (`FindingsWorkbenchPage` at `/cases/:caseId/findings`) integrated into sidebar navigation and workspace routing.
   - Epistemic classification preservation with prominent legal disclaimer banner and visual styling across `OBSERVED_FACT`, `AUTOMATED_INDICATOR`, `ANALYTICAL_INTERPRETATION`, and `INVESTIGATOR_CONCLUSION`.
   - Multi-facet filter toolbar: epistemic classification, severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFORMATIONAL`), review status, and subsystem source; search across title, description, rule, or finding ID.
   - Finding detail panel with heuristic score caveats, known limitations, coordinate provenance links to original documents, and supporting vs. contradictory evidence keys.
   - Human review adjudication workflow with modal supporting 5 review actions (`CONFIRM_OBSERVATION`, `DISMISS_FALSE_POSITIVE`, `MARK_INCONCLUSIVE`, `REQUEST_MORE_EVIDENCE`, `MARK_NEEDS_REVIEW`), mandatory rationale, asserted reviewer identity, and double-submission safeguards.
   - Append-only review ledger displaying historical transitions with audit event recording.
   - Dossier review-readiness drawer with audit metrics, new draft compilation, snapshot finalization sealing canonical SHA-256 hash, and vector PDF / structured JSON exports.
   - Comprehensive test suite: 80 Vitest tests across 20 suites (100% pass rate) and clean production build.
15. **End-to-End Investigation Integration & Reliability (Phase 3E):**
   - Validated and hardened the complete 10-step investigator case lifecycle from case creation to finalized dossier export.
   - End-to-end integration test (`tests/integration/test_phase_3e_investigation_lifecycle.py`) verifying ingestion, duplicate handling, original document download, PDF structural forensics, OCR text & token extraction, classification, structured field extraction, entity resolution, relationship detection, cross-document consistency analysis, processing history, graph projection with BFS neighborhood and pathfinding, aggregated findings triage, append-only human review persistence, 12-section dossier generation, canonical SHA-256 seal computation and equality verification, deterministic vector PDF export, and structured JSON export.
   - Archived-case safeguards strictly rejecting mutations on archived cases (HTTP 400/422) while preserving read-only download and export access.
   - Complete epistemic integrity audit eliminating non-neutral terminology across all user-facing components and documentation.
16. **Grounded AI Investigation Assistant (Phase 4A):**
   - Controlled, evidence-grounded AI assistant operating strictly on authoritative case records.
   - Multi-subsystem case evidence retriever (`CaseEvidenceRetriever`) compiling documents, forensic findings, consistency findings, entities, relationships, evidence nodes, and reviews with automatic PII masking.
   - Strict case isolation with 404 security barriers preventing cross-case evidence leakage.
   - Read-only querying permitted on archived cases (`CaseStatus.ARCHIVED`).
   - Multi-layered prompt injection defenses treating document text as untrusted data within `<case_evidence>` XML tags.
   - Decoupled provider layer (`LlmProviderProtocol`) supporting deterministic offline testing via `MockLlmProvider` and self-hosted or OpenAI-compatible endpoints via `HttpLlmProvider`.
   - Strict epistemic separation in output schema (Observed Facts, Automated Indicators, Analytical Interpretations, Contradictory Evidence, Unresolved Questions, Limitations).
   - Citation grounding validation: all citations (`[E-1]`, `[E-2]`) cross-referenced against real retrieved records, ungrounded citations purged, and valid citations enriched with deep links (`target_route`).
   - Interactive investigator frontend (`AssistantPage` at `/cases/:caseId/assistant`) with 6 quick task category chips, citation cards, epistemic breakdown accordions, follow-up query suggestions, and prominent evidentiary boundary disclosures.
17. **AI Reliability, Grounding & Adversarial Evaluation (Phase 4B):**
   - Deterministic claim-level grounding engine (`ClaimGroundingValidator`) with token correspondence, subsystem consistency, spatial/page matching, and ungrounded citation pruning.
   - Contradiction omission detection measuring suppression or omission of retrieved cross-document and forensic conflicts.
   - Version-controlled benchmark dataset (`tests/fixtures/eval/benchmark_scenarios.py`) with 10 synthetic scenarios spanning invoices, candidate relationships, contradictions, follow-ups, insufficient evidence, adversarial prompt injections, and PII exfiltration.
   - Automated evaluation harness (`AssistantReliabilityEvaluator`) producing comprehensive quantitative grounding reports (`ScenarioEvaluationResult`, `BenchmarkSummary`).
   - Multi-layered prompt injection defenses neutralizing injection payloads across OCR text, conversation history, entity names, and metadata.
   - Systematic PII sanitization pipeline (`sanitization.py`) neutralizing PANs, Aadhaar, SSNs, EINs, credit cards, and split/spaced account numbers prior to LLM submission.
   - Provider resilience and error hierarchy (`ProviderConnectionError`, `ProviderTimeoutError`, `ProviderRateLimitError`, `ProviderPayloadLimitError`, `ProviderResponseError`) with payload size guards (256KB request, 512KB response) and exponential backoff.
   - Frontend reliability transparency: explicit provider failure alert banners with retry guidance, insufficient evidence notices, and grounded citation verification badges.
   - 100% test pass rate across 40 assistant tests and 89 frontend tests.
18. **Independent Evaluation Integrity & Safety Closure (Phase 4B.1):**
   - Explicit mathematical separation of Citation Resolution, Lexical Relevance, and Claim Support (`SUPPORTED`, `CONTRADICTED`, `UNVERIFIED`). Entity mentions alone no longer validate substantive claims without corroborating record evidence.
   - Deterministic reversal detection catching numerical discrepancies, payment status inversions, candidate relationship upgrades, and document attribution errors.
   - Independent benchmark negative controls (7 test scenarios) verifying that contradictory or fabricated assertions fail the grounding validation gate.
   - Reasoning manipulation defenses preventing adversarial injection attempts to suppress contradiction findings, upgrade automated indicators to conclusions, or treat candidate relationships as confirmed.
   - False-positive PII masking prevention preserving legitimate evidence identifiers (`INV-...`, `PO-...`, `TXN-...`, `REF-...`) and dates.
   - Resource-bounded streaming provider enforcing 512KB response limits via chunk-level streaming, honoring `Retry-After` headers, failing fast on non-retryable 4xx errors, and sanitizing credentials.
   - Truthful frontend wording replacing misleading "Grounded" badge with "Citations Linked ({count})", "Insufficient Evidence", and transparent investigator notices.
   - 100% test pass rate across 55 assistant tests and 436 backend tests total.

---

## 3. Active Pre-Release Disclosures

- **Status:** Pre-release v0.1.0 under active engineering.
- **Backend Readiness:** Production-grade modular monolith architecture with complete REST API coverage across 28+ endpoints.
- **Frontend / UI:** Phase 3A (investigator application shell), Phase 3B.1 (document inventory and upload), Phase 3B.2 (visual PDF canvas and OCR inspector), Phase 3C (interactive Evidence Graph canvas), Phase 3D (Unified Findings Workbench), Phase 3E (End-to-End Investigation Integration & Reliability), and Phase 4A (Grounded AI Investigation Assistant) are operational. All backend capabilities remain accessible via the OpenAPI documentation (`/docs`, `/redoc`).
- **Language Scope:** Document OCR and entity extraction models are currently configured and verified for Latin/English alphanumeric documents. Multilingual expansion (Devanagari, Arabic, CJK) is scheduled for Phase 4.
- **Deployment Scope:** Single-node CPU execution is verified; distributed multi-node task queues (Celery/Redis) are planned for enterprise scale.

