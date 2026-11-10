# EVIDEXA Product Roadmap

**Intelligence Behind Every Evidence.**  
*Product Version: 0.1.0 (Pre-Release)*

---

## 1. Roadmap Architecture

The EVIDEXA roadmap is structured into four sequential phases, progressing from deep mathematical file forensics to high-level investigator workflows and enterprise deployment:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     PHASE 1     │     │     PHASE 2     │     │     PHASE 3     │     │     PHASE 4     │
│ Core Foundation │────>│ Understanding & │────>│  Investigation  │────>│   Enterprise    │
│  & PDF Forensics│     │ Cross-Doc Engine│     │  Workspace & UI │     │ Scale & Defense │
│   [COMPLETED]   │     │   [COMPLETED]   │     │   [COMPLETED]   │     │  [IN PROGRESS]  │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## 2. Phase Breakdown

### Phase 1: Core Foundation & Digital PDF Forensics `[COMPLETED]`
- [x] Modular monolith architecture with strict domain layer isolation (zero framework dependencies).
- [x] Case lifecycle management with soft archival (`CaseStatus.ARCHIVED`) prohibiting destructive deletion.
- [x] Ephemeral analysis snapshots with double pre/post-analysis SHA-256 immutability verification.
- [x] Process-isolated subprocess worker (`worker.py`) with 30-second supervisor timeouts and bounded I/O.
- [x] Structural PDF analysis: XREF table reconstruction, incremental update parsing, object stream inspection.
- [x] Font and content stream anomaly detection.
- [x] Cryptographic append-only audit ledger with SHA-256 hash chaining and sequence verification.
- [x] Automated recovery of stale orphaned jobs upon application startup.

### Phase 2: Visual Forensics, Document Understanding & Cross-Doc Engine `[COMPLETED]`
- [x] Error Level Analysis (ELA) and 2D-DCT copy-move forgery detection.
- [x] Hybrid adaptive OCR routing (PDFium vector text vs. RapidOCR ONNX optical character recognition).
- [x] Normalized canonical coordinate system (`NORMALIZED_0_1`) invariant across document rotations.
- [x] Schema-driven structured extraction for invoices, receipts, purchase orders, and bank statements.
- [x] Exact financial decimal quantization (currency minor units) eliminating floating-point rounding errors.
- [x] Zero plaintext PII persistence (automatic masking of bank accounts, PANs, Aadhaar numbers).
- [x] Deterministic entity resolution across documents (`ORGANIZATION`, `PERSON`, `TAX_ID`, `ACCOUNT`, `AMOUNT`).
- [x] Relationship Ontology V2: directed Subject-Predicate-Object semantics with explicit status vs. score separation.
- [x] Separation of discrete invoice billing events (`INVOICED`) from contractual supply arrangements (`SUPPLIES`).
- [x] Contradiction persistence preserving conflicting evidence signals under manual investigator review.
- [x] Cross-Document Consistency Engine evaluating 6 deterministic rule families (Invoice/Receipt, PO/Invoice, Bank Statement/Invoice, Identity/Tax ID, Duplicates/Conflicts, Temporal Lifecycle).
- [x] Unified Evidence Graph query layer: In-memory projection of heterogeneous evidence records, bounded neighborhood BFS, and cycle-safe path search without secondary database persistence.
- [x] Findings Aggregation & Evidence Dossier Layer (Phase 2D): 12-section investigation dossier generator, 4-tier epistemic classification, append-only investigator reviews, deterministic vector PDF export (`pikepdf`), structured JSON export, and SHA-256 canonical content hashing.
- [x] Database migrations through `008_evidence_dossier` with full backward compatibility and rollback verification.

### Phase 3: Investigation Workspace, Interactive Graph & Dossier Generator `[COMPLETED]`
- [x] **Phase 3A: Investigator Frontend Foundation & Application Shell `[COMPLETED]`**
  - [x] Production React 18, TypeScript, Vite, Tailwind CSS application shell in `frontend/`.
  - [x] Official brand identity (`docs/BRAND_GUIDE.md`): Midnight, Charcoal, Slate, Electric Cyan palette and layered geometric SVG mark.
  - [x] Accessible status badge components with mandatory semantic icon + label pairing.
  - [x] Typed API client with central base URL configuration, RFC 7807 error envelopes, and TanStack React Query cache invalidation.
  - [x] Global navigation shell with active case context switcher and breadcrumbs.
  - [x] Investigation Case Management catalog, status filtering, and creation modal.
  - [x] Case Overview Dashboard with real-time forensic metrics and explicit uncalculated states.
  - [x] Production build verification and component test suite (11 Vitest tests).
- [x] **Phase 3B.1: Document Inventory, Upload & Processing Workspace `[COMPLETED]`**
  - [x] Case-scoped document inventory catalog with pagination, search by name/ID/hash, format filtering, and multi-criteria sorting.
  - [x] Secure document upload modal with drag-and-drop, 50MB file size limits, extension validation, duplicate detection, and examiner attribution.
  - [x] In-depth slide-over Document Detail Drawer with copyable full SHA-256 digests, storage metadata, runs history, and raw evidence download.
  - [x] Real processing execution controls for PDF structural analysis, visual ELA, hybrid OCR, document classification, and structured field extraction.
  - [x] Backend single-document endpoints (`GET /cases/{case_id}/documents/{document_id}` and `GET /cases/{case_id}/documents/{document_id}/download`).
  - [x] Production frontend test coverage expanded to 24 Vitest tests (100% passing across 9 test suites).
- [x] **Phase 3B.2: Visual Document Heatmap & OCR Inspector `[COMPLETED]`**
  - [x] Multi-page visual PDF canvas viewer (`pdfjs-dist`) with synchronized zoom (25%–300%), rotation (90° clockwise increments), fit-to-width, and reset controls.
  - [x] Canonical coordinate transformation contract (`NORMALIZED_0_1`) mapping top-left normalized coordinates accurately to canvas layout pixels across zoom and rotation.
  - [x] Interactive OCR token bounding box overlay with hover text inspector, confidence metrics, and bidirectional click-to-highlight navigation.
  - [x] Schema-driven structured field extraction inspector with automatic PII / sensitive financial identifier masking (accounts, PAN, tax IDs) and "Locate on Page" coordinates.
  - [x] Forensic findings and visual anomaly inspector with non-verdict forensic caveat banners, severity distribution filters, and direct evidence provenance links.
  - [x] Visual Error Level Analysis (ELA) heatmap raster overlay with opacity blend and dedicated artifact retrieval endpoint.
  - [x] 3-region workspace (Thumbnail Strip, Document Canvas Viewer, Multi-tab Inspector) with responsive collapsible panels.
  - [x] Comprehensive test coverage: 51 Vitest tests across 16 suites (100% passing) and verified clean production build.
- [x] **Phase 3C: Interactive Evidence Graph Canvas `[COMPLETED]`**
  - [x] High-performance interactive graph visualization workspace (`EvidenceGraphPage` at `/cases/:caseId/graph`) powered by `@xyflow/react` and `@dagrejs/dagre`.
  - [x] Hierarchical Dagre layout engine with automatic LR rank calculation and bidirectional handle routing.
  - [x] 16 custom typed node configurations with automated PII masking on sensitive financial identifiers and direct page coordinate badges.
  - [x] Evidentiary status edge styling with distinct canonical strokes (`CONFIRMED` cyan, `CANDIDATE` amber dashed, `CONTRADICTED` crimson dashed, `UNRESOLVED` slate dotted, `REJECTED` strike-through).
  - [x] Investigation controls bar with debounced node search, autocomplete dropdown, node-type and status multi-filters, fit-to-view, and Dagre re-layout triggers.
  - [x] Deep Details Inspector for node metadata and edge evidentiary rationale with 1-click cross-workspace navigation to visual document examination (`/cases/:caseId/documents/:documentId/examine`).
  - [x] In-situ 2-hop BFS neighborhood expansion (`GET /cases/{case_id}/graph/nodes/{node_id}/neighbors`) without reloading entire case projection.
  - [x] Bounded multi-hop directed pathfinding modal (`GET /cases/{case_id}/graph/paths`) with canvas path highlights.
  - [x] Comprehensive test coverage: 63 Vitest tests across 18 suites (100% passing) and verified clean production build.
- [x] **Phase 3D: Unified Findings & Investigator Review Workbench `[COMPLETED]`**
  - [x] Unified case findings triage workspace (`FindingsWorkbenchPage` at `/cases/:caseId/findings`) integrated into sidebar navigation and routing.
  - [x] Epistemic classification preservation (`OBSERVED_FACT`, `AUTOMATED_INDICATOR`, `ANALYTICAL_INTERPRETATION`, `INVESTIGATOR_CONCLUSION`) with prominent legal triage notice.
  - [x] Multi-facet filtering toolbar (epistemic classification, severity, review status, subsystem source, text search) with active filter counters and reset.
  - [x] Deep finding detail panel with forensic explanation breakdown, heuristic confidence score caveats, known limitations, coordinate provenance links, and supporting vs. contradictory evidence keys.
  - [x] Human review adjudication modal with 5 review actions (`CONFIRM_OBSERVATION`, `DISMISS_FALSE_POSITIVE`, `MARK_INCONCLUSIVE`, `REQUEST_MORE_EVIDENCE`, `MARK_NEEDS_REVIEW`), mandatory rationale, asserted reviewer identity, and double-submission prevention.
  - [x] Append-only review ledger displaying chronological transitions with backend audit logging (`REVIEW_DECISION_RECORDED`).
  - [x] Dossier review-readiness drawer tracking audit metrics, compiling new drafts, sealing snapshots with canonical SHA-256 hash, and vector PDF / structured JSON downloads.
  - [x] Comprehensive test coverage: 80 Vitest tests across 20 suites (100% passing) and verified clean production build.
- [x] **Phase 3E: End-to-End Investigation Integration & Reliability `[COMPLETED]`**
  - [x] Full 10-step investigation lifecycle integration: case creation, document ingestion, multi-pipeline analysis, OCR/extraction inspection, evidence graph exploration, findings review, adjudication persistence, dossier draft generation, cryptographic freeze sealing, and export verification.
  - [x] Archived-case mutation safeguards across documents, forensic processing, review recording, and dossier operations with HTTP 400/422 barriers.
  - [x] Cryptographic SHA-256 seal computation and canonical content hash equality verification (`recomputed_hash == content_hash`).
  - [x] Deterministic vector PDF and structured JSON artifact export with strict non-adjudication legal disclaimers.
  - [x] Repeatable end-to-end integration test suite (`tests/integration/test_phase_3e_investigation_lifecycle.py`) verifying full workflow without mocked data.

### Phase 4: Grounded AI Assistant & Enterprise Multi-Agent Intelligence `[IN PROGRESS]`
- [x] **Phase 4A: Grounded AI Investigation Assistant `[COMPLETED]`**
  - [x] Case-bounded evidence retriever (`CaseEvidenceRetriever`) compiling documents, forensic findings, consistency findings, entities, relationships, evidence nodes, and reviews with PII minimization.
  - [x] Multi-layered prompt injection defenses (untrusted data encapsulation in `<case_evidence>` XML boundaries, anti-override and anti-execution system instructions).
  - [x] Pluggable provider abstraction (`MockLlmProvider` for deterministic offline testing with 0 API keys; `HttpLlmProvider` for OpenAI/Ollama compatible endpoints).
  - [x] Strict epistemic separation in output schema (Observed Facts, Automated Indicators, Analytical Interpretations, Contradictory Evidence, Unresolved Questions, Limitations).
  - [x] Citation grounding verification (validation against real retrieved records, pruning ungrounded citations, deep link generation).
  - [x] Interactive investigator assistant interface (`AssistantPage` at `/cases/:caseId/assistant`) with 6 quick task category chips, citation cards, epistemic breakdown accordions, follow-up query suggestions, and evidentiary boundary disclosures.
  - [x] Comprehensive test coverage: 15 backend unit and integration tests (100% pass), 7 frontend component tests (100% pass), and clean production build.
- [x] **Phase 4B: AI Reliability, Grounding & Adversarial Evaluation `[COMPLETED]`**
  - [x] Deterministic claim-level evidence grounding engine (`ClaimGroundingValidator`) with token correspondence, record verification, subsystem validation, and spatial/page reference enforcement.
  - [x] Contradiction omission detection measuring suppression or omission of retrieved cross-document and forensic conflicts.
  - [x] Repeatable benchmark evaluation dataset (`tests/fixtures/eval/benchmark_scenarios.py`) with 10 version-controlled scenarios spanning standard workflows, edge cases, and adversarial vectors.
  - [x] Headless evaluation harness (`AssistantReliabilityEvaluator`) producing comprehensive quantitative accuracy, grounding, and resistance reports.
  - [x] Multi-layered prompt injection hardening against OCR text injections, conversation context manipulations, metadata attacks, and entity name exfiltrations.
  - [x] Systematic sensitive data protection & PII minimization pipeline (`sanitization.py`) neutralizing PANs, Aadhaar, SSNs, EINs, credit cards, and split/spaced account numbers prior to LLM submission.
  - [x] Provider resilience and error discrimination (`ProviderConnectionError`, `ProviderTimeoutError`, `ProviderRateLimitError`, `ProviderPayloadLimitError`, `ProviderResponseError`) with payload size guards (256KB request, 512KB response) and exponential backoff.
  - [x] Frontend transparency: explicit provider failure alert banners with retry guidance, insufficient evidence notices, and grounded citation verification badges.
  - [x] Verification test suite: 40 backend assistant unit & integration tests (100% pass) and 23 frontend test suites (89 tests, 100% pass).
- [x] **Phase 4B.1: Independent Evaluation Integrity & Safety Closure `[COMPLETED]`**
  - [x] Claim-level grounding vs. relevance mathematical separation (`ClaimSupportStatus.SUPPORTED`, `CONTRADICTED`, `UNVERIFIED`). Isolated entity mentions no longer falsely validate substantive contract or transactional claims.
  - [x] Deterministic reversal detection catching numerical discrepancies, payment status inversions, candidate relationship upgrades, and document attribution errors.
  - [x] Independent benchmark negative controls (7 test scenarios) verifying that contradictory, incorrect, or fabricated claims fail the grounding gate deterministically.
  - [x] Reasoning manipulation defense neutralizing prompt injection attempts to suppress contradictions, upgrade indicators to conclusions, or treat candidate relationships as confirmed.
  - [x] PII false-positive prevention preserving legitimate evidence identifiers (`INV-...`, `PO-...`, `TXN-...`, `REF-...`) and dates from destruction.
  - [x] Bounded streaming provider limits enforcing 512KB response streaming limits before memory buffering, honoring `Retry-After` headers, failing fast on non-retryable 4xx errors, and sanitizing credentials.
  - [x] Truthful frontend wording replacing misleading "Grounded" badge with "Citations Linked ({count})", "Insufficient Evidence", and transparent investigator notices.
  - [x] Verification test suite: 55 backend assistant unit & integration tests (100% pass), 436 backend tests total (100% pass), and 89 frontend tests (100% pass).
- [ ] **Phase 4C: Multi-Case Applicant Correlation & Fraud Ring Detection `[PLANNED]`**
  - [ ] Cross-case privacy-preserving entity correlation and ring detection.
- [ ] **Phase 4D: Multilingual & Multimodal Document Intelligence `[IN PROGRESS]`**
  - [x] **Phase 4D.1: Multilingual Document Intelligence Research & Architecture `[COMPLETED]`**
    - [x] Comprehensive OCR engine evaluation (PaddleOCR, Tesseract, EasyOCR, docTR, RapidOCR, Surya).
    - [x] Independent open-source license audit (code vs model weights vs datasets; CC BY-NC-SA and GPL rejection).
    - [x] Hardware feasibility modeling for 16 GB RAM CPU-only execution (ONNX thread pooling, peak memory ceilings).
    - [x] Multilingual OCR architecture blueprint (Unicode script detection, dynamic recognition routing, contract extensions).
    - [x] Traceable & reversible normalization design (Devanagari numerals, Indian comma grouping, ISO currency/dates).
    - [x] 100% synthetic privacy-preserving benchmark dataset specification (`EVIDEXA-BENCH-MULTILINGUAL-V1`).
    - [x] Architecture Decision Record (ADR-001) recommending RapidOCR Devanagari ONNX + Tesseract fallback.
  - [ ] **Phase 4D.2: Script Detection & Multilingual OCR Adapter `[PLANNED]`**
  - [ ] **Phase 4D.3: Hindi-English Extraction & Traceable Normalization `[PLANNED]`**
  - [ ] **Phase 4D.4: Frontend Multilingual OCR Inspection & Font Rendering `[PLANNED]`**
  - [ ] **Phase 4D.5: Synthetic Benchmarking, Performance & Safety Hardening `[PLANNED]`**
  - [ ] Regional Indian language expansion (Priority 2: Bengali, Marathi, Tamil, Telugu, Gujarati, Punjabi, Urdu).
  - [ ] International script expansion (Priority 3: Arabic, Chinese, Japanese, Korean).
- [ ] **Phase 4E: Enterprise Identity, Task Queues & Scalability `[PLANNED]`**
  - [ ] Enterprise identity integration: OpenID Connect (OIDC), SAML 2.0, and role-based access control (RBAC).
  - [ ] High-throughput distributed Celery / Redis task workers for large-scale enterprise batch ingestion.
  - [ ] Hardware-accelerated inference profiles (NVIDIA TensorRT / OpenVINO) for high-density document scanning.

