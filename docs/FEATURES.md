# EVIDEXA Feature Matrix & Capability Status

**Intelligence Behind Every Evidence.**  
*Status Assessment Date: November 2026*

This document provides an honest, granular breakdown of the EVIDEXA capability matrix. Every feature is explicitly designated with its current engineering status:
- **`[IMPLEMENTED]`**: Fully implemented, unit/integration tested, and operational in the current codebase.
- **`[IN PROGRESS]`**: Partially implemented or currently undergoing hardening and active engineering.
- **`[PLANNED]`**: Designed and scheduled in the product roadmap.
- **`[UNAVAILABLE]`**: Explicit non-goal or out of scope for the current architectural cycle.

---

## 1. Document Ingestion & Understanding

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Digital PDF Ingestion** | `[IMPLEMENTED]` | Ingests digital PDFs via FastAPI multipart upload with MIME verification, magic-byte checks, and master storage isolation. |
| **Scanned Document Ingestion** | `[IMPLEMENTED]` | Supports image-based PDFs, PNG, JPEG, and TIFF files up to 50 MB with resource limits and decompression bomb protections. |
| **PDFium Digital Text Extraction** | `[IMPLEMENTED]` | Fast extraction of embedded digital PDF text tokens with exact font and character bounding boxes via `pypdfium2`. |
| **RapidOCR Scanned OCR** | `[IMPLEMENTED]` | Deep optical character recognition using ONNX Runtime with CPU-optimized English/Latin text recognition models. |
| **Hybrid Adaptive OCR Routing** | `[IMPLEMENTED]` | Evaluates per-page character density and raster area to automatically route vector pages to PDFium and scanned pages to RapidOCR. |
| **Canonical Coordinate System** | `[IMPLEMENTED]` | Translates all engine bounding boxes into `NORMALIZED_0_1` (top-left $[0.0, 0.0]$, bottom-right $[1.0, 1.0]$) invariant across rotations and resolutions. |
| **Page Classification (Rule-Based)** | `[IMPLEMENTED]` | Classifies documents into `INVOICE`, `RECEIPT`, `BANK_STATEMENT`, `TAX_FORM`, `IDENTITY_DOCUMENT`, `CONTRACT`, `UNKNOWN`. |
| **Structured Field Extraction** | `[IMPLEMENTED]` | Extracts structured fields based on schema definitions (`invoice_v1`, `receipt_v1`, `bank_statement_v1`). |
| **Exact Financial Decimal Precision** | `[IMPLEMENTED]` | Amounts quantized to exact Python `Decimal` values according to currency minor unit rules (USD 2, JPY 0, KWD 3). Zero floating-point rounding errors. |
| **Zero Plaintext PII Persistence** | `[IMPLEMENTED]` | Masks sensitive bank accounts (`****{last4}`), PANs, and Aadhaar numbers before relational storage, logs, or JSON artifacts. |
| **Multilingual OCR (Devanagari, Arabic, CJK)** | `[PLANNED]` | Multilingual OCR dictionaries and language detection models. Currently restricted to Latin/English. |
| **Fine-Tuned Multimodal Layout Model** | `[PLANNED]` | Deep learning layout segmentation (LayoutLMv3 / Donut) for complex nested tables and borderless grid reconstruction. |

---

## 2. Digital Document Forensics

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Subprocess-Isolated PDF Analysis** | `[IMPLEMENTED]` | PDF structural analysis runs in isolated child process (`worker.py`) with 30s timeout, bounded I/O, and path sanitization. |
| **Ephemeral Analysis Snapshots** | `[IMPLEMENTED]` | Analysis runs on temporary read-only snapshots with double SHA-256 integrity verification before and after execution. |
| **PDF Incremental Update Analysis** | `[IMPLEMENTED]` | Detects appended incremental updates, hidden object revisions, and modified trailer dictionaries. |
| **Font & Stream Forensics** | `[IMPLEMENTED]` | Flags anomalous font encodings, inconsistent embedded fonts, and unexpected stream alterations. |
| **Qualitative Forensic Confidence** | `[IMPLEMENTED]` | Preserves raw upstream categorical confidence (`high`, `medium`, `low`, `unknown`) without fabricating arbitrary numeric floats. |
| **Coordinate-Honest Forensic Output** | `[IMPLEMENTED]` | Non-spatial structural findings report `bounding_box=None` and `coordinate_system=None`. Spatial anomalies retain exact pixel coordinates. |
| **Error Level Analysis (ELA)** | `[IMPLEMENTED]` | Evaluates JPEG compression artifact discrepancies across image resaves to highlight digitally spliced regions. |
| **DCT Copy-Move Forgery Detection** | `[IMPLEMENTED]` | Identifies duplicated image patches and cloned text blocks using 2D Discrete Cosine Transform block clustering. |
| **Double Immutability Safeguards** | `[IMPLEMENTED]` | Aborts workflow and logs audit security event if either snapshot or master file hash changes during analysis. |
| **Stale Run Auto-Recovery** | `[IMPLEMENTED]` | Lifespan coordinator detects orphaned `RUNNING` forensic jobs on server startup and recovers them to `FAILED` with audit logging. |
| **Deep Neural GAN/Inpainting Detector** | `[PLANNED]` | Specialized deep learning models to detect generative AI fill and synthetic object inpainting in scanned documents. |
| **Printer Micro-Steganography / Tracking Dots**| `[UNAVAILABLE]` | Laser printer machine identification code (MIC) decoding is out of scope for the current platform release. |

---

## 3. Contextual & Cross-Document Intelligence

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Deterministic Entity Resolution** | `[IMPLEMENTED]` | Resolves `ORGANIZATION`, `PERSON`, `TAX_IDENTIFIER`, `INVOICE_REF`, `BANK_ACCOUNT`, `AMOUNT` across files. |
| **Match Categorization** | `[IMPLEMENTED]` | Distinguishes exact matches, normalized matches, candidate matches, conflicting identities, and insufficient evidence. |
| **Directed Relationship Ontology (V2)** | `[IMPLEMENTED]` | Directed Subject-Predicate-Object semantics (`ISSUED`, `BILLED_TO`, `INVOICED`, `HELD_BY`, `SUPPLIES`, `DUPLICATE_OF`, etc.). |
| **Commercial Invariant Protection** | `[IMPLEMENTED]` | Invoice co-occurrence creates `INVOICED`; ongoing `SUPPLIES` relationships require explicit contract clause evidence. |
| **Score vs Status Separation** | `[IMPLEMENTED]` | Status (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`) is governed strictly by evidentiary rules, not heuristic weights. |
| **Duplicate Identity Semantics** | `[IMPLEMENTED]` | Distinguishes `BYTE_IDENTICAL` (SHA-256 digest equality) from `VISUALLY_SIMILAR` and `SEMANTICALLY_SIMILAR`. |
| **Contradiction Precedence** | `[IMPLEMENTED]` | Conflicting tax IDs or mismatched currencies immediately override similarity, marking relationships `CONTRADICTED` (score 0.0). |
| **Non-Fabrication of Bank Transactions**| `[IMPLEMENTED]` | Transaction settlement edges are never fabricated when documents conform to summary-only schemas (`bank_statement_v1`). |
| **Historical Data Migration (006)** | `[IMPLEMENTED]` | Alembic migration 006 automatically maps historical legacy predicates with full rollback support. |
| **Cross-Case Ring Detection** | `[PLANNED]` | Anonymized applicant network clustering across multiple cases scheduled for Phase 3. |
| **Autonomous Fraud Verdict Engine** | `[UNAVAILABLE]` | EVIDEXA explicitly rejects autonomous fraud determination. All legal and risk conclusions require human investigator adjudication. |

---

## 4. Cross-Document Consistency Engine

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Deterministic Consistency Rule Engine** | `[IMPLEMENTED]` | Modular deterministic engine evaluating cross-document rule families with bounded pairwise matching and case isolation. |
| **Invoice vs Receipt Total Reconciliation** | `[IMPLEMENTED]` | Evaluates gross invoice totals against receipt payment totals using strict Decimal arithmetic without floating-point distortion. |
| **Invoice vs Receipt Reference & Party Consistency** | `[IMPLEMENTED]` | Compares invoice numbers with receipt references, and supplier legal names with retail merchant trading names. |
| **Purchase Order vs Invoice Reconciliation** | `[IMPLEMENTED]` | Compares PO references, supplier/buyer parties, line-item quantities, unit prices, subtotals, and gross totals. |
| **Bank Statement Transaction Matching** | `[IMPLEMENTED]` | Evaluates potential bank settlement records against invoices. Flags ambiguous multiple matching transactions and date anomalies. |
| **Cross-Document Supplier & Tax ID Consistency**| `[IMPLEMENTED]` | Detects conflicting tax IDs for the same legal vendor. Treats missing tax identifiers as `INSUFFICIENT_EVIDENCE`, never false contradiction. |
| **Duplicate vs Contradictory Record Analysis** | `[IMPLEMENTED]` | Distinguishes `BYTE_IDENTICAL` duplicates from conflicting records reusing the same invoice number with divergent amounts or vendors. |
| **Lifecycle Temporal Sequence Verification** | `[IMPLEMENTED]` | Verifies chronological ordering across POs, invoices, and payment receipts. Flags invoices predating their authorizing PO. |
| **Five-Valued Evidentiary Semantics** | `[IMPLEMENTED]` | Every check outputs `CONSISTENT`, `INCONSISTENT`, `POTENTIAL_ANOMALY`, `INSUFFICIENT_EVIDENCE`, or `NOT_APPLICABLE` with explainable rationale. |
| **Sub-Document Coordinate & Provenance Traceability**| `[IMPLEMENTED]`| Findings preserve page indices, normalized bounding boxes, original extracted strings, and Decimal normalized values. |
| **Append-Only Human Review Workflow** | `[IMPLEMENTED]` | Supports `CONFIRM_INCONSISTENCY`, `DISMISS`, `MARK_INSUFFICIENT_EVIDENCE`, and `REQUEST_MORE_EVIDENCE` with mandatory justification comments. |

---

## 5. Evidence Intelligence & Provenance Graph

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Unified Evidence Graph Projection** | `[IMPLEMENTED]` | In-memory projection linking cases, documents, evidence nodes, forensic findings, consistency findings, extracted entities, and candidate matches into a single unified model without a second database source of truth. |
| **Grounding & Provenance Traceability** | `[IMPLEMENTED]` | Every node and edge traces directly to its authoritative source relational record, document ID, page number, bounding box, and generating component. |
| **Canonical Predicates & Status Preservation** | `[IMPLEMENTED]` | Directed Subject-Predicate-Object semantics preserving explicit evidentiary statuses (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`, `REJECTED`) and status determination methods. |
| **Bounded Graph Querying & Pagination** | `[IMPLEMENTED]` | Filterable case graph retrieval by node types, relationship predicates, statuses, and document IDs with explicit limits and truncation indicators. |
| **Cycle-Safe Neighborhood Exploration** | `[IMPLEMENTED]` | Bounded k-hop BFS expansion around seed nodes with hard safety caps preventing infinite loops on cyclic topologies. |
| **Evidentiary Pathfinding Engine** | `[IMPLEMENTED]` | Directed path exploration between two arbitrary nodes with configurable max depth, cycle prevention, and `confirmed_only` filtering. |
| **Zero Plaintext PII in Graph Representations** | `[IMPLEMENTED]` | Automated masking of sensitive bank accounts, financial identifiers, and tax sequences in graph display labels. |
| **Contradiction Persistence** | `[IMPLEMENTED]` | Pre-existing contradictory evidence signals remain completely visible in evidence payloads even after manual human review confirmation. |
| **Hash-Chained Audit Ledger** | `[IMPLEMENTED]` | Tamper-evident audit log with SHA-256 hash chaining and sequence verification for all operational and review events. |
| **Artifact Storage Verification** | `[IMPLEMENTED]` | Serialized analysis and relationship artifacts verified via synchronous SHA-256 recalculation upon retrieval. |
| **Interactive Graph Visualization** | `[IMPLEMENTED]` | Visual node-and-edge investigation canvas in web UI powered by `@xyflow/react` and `@dagrejs/dagre` with real-time filtering, neighborhood expansion, and path exploration. |

---

## 6. Investigation Workspace & Reporting

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Case Management & Isolation** | `[IMPLEMENTED]` | Case creation, listing, status updates, and soft archival (`CaseStatus.ARCHIVED`) with strict single-case isolation. |
| **Single-Case 404 Security Barrier** | `[IMPLEMENTED]` | Cross-case entity or relationship access attempts raise `SecurityException` and return HTTP 404. |
| **Human Match & Relationship Review** | `[IMPLEMENTED]` | Dedicated REST review endpoints with mandatory reviewer ID, timestamp, and audit trail generation. |
| **REST API OpenAPI Specification** | `[IMPLEMENTED]` | Comprehensive Swagger UI (`/docs`) and ReDoc (`/redoc`) documentation covering all case, forensic, OCR, relationship, consistency, graph, and dossier routes. |
| **Unified Findings Aggregation** | `[IMPLEMENTED]` | Aggregates forensic findings, consistency findings, relationship anomalies, and candidate conflicts with epistemic classification. |
| **Append-Only Investigator Reviews** | `[IMPLEMENTED]` | Records reviewer assertions (`CONFIRM_OBSERVATION`, `DISMISS_FALSE_POSITIVE`, etc.) with reviewer identity and mandatory rationale. |
| **12-Section Formal Dossier Generator** | `[IMPLEMENTED]` | Structured case report across 12 analytical sections with deterministic SHA-256 content hashing and versioning. |
| **Deterministic Vector PDF Export** | `[IMPLEMENTED]` | Generates multi-page, structured vector PDFs using existing core `pikepdf` dependency (`deterministic_id=True`) with EVIDEXA branding, headers, tables, and legal disclaimers. |
| **Structured JSON Dossier Export** | `[IMPLEMENTED]` | Serializes complete dossier chapters, document inventories, evidence references, review decisions, and legal disclaimers for interoperable data exchange. |
| **Investigator Application Shell (Phase 3A)** | `[IMPLEMENTED]` | React 18, TypeScript, Vite, Tailwind CSS shell with brand identity (Midnight/Charcoal/Slate/Cyan), active case switcher, and breadcrumb header. |
| **Case Overview Dashboard (Phase 3A)** | `[IMPLEMENTED]` | Real-time case dashboard showing authentic metrics (documents, findings, consistency runs, relationships, dossiers) with explicit uncalculated states. |
| **Case Management Interface (Phase 3A)** | `[IMPLEMENTED]` | Case workspace catalog, search, status filtering (`ACTIVE`, `UNDER_REVIEW`, `COMPLETED`, `ARCHIVED`, `DRAFT`), and new case modal. |
| **Document Inventory & Ingestion Workspace (Phase 3B.1)** | `[IMPLEMENTED]` | Case-scoped document inventory, drag-and-drop secure upload (50 MB cap, MIME/extension checks), full SHA-256 inspection, duplicate badges, and original file download. |
| **Document Processing Controls (Phase 3B.1)** | `[IMPLEMENTED]` | One-click execution controls for PDF structural forensics, visual ELA, hybrid OCR, document classification, and structured field extraction with in-flight safeguards. |
| **Visual Document Heatmap & OCR Inspector (Phase 3B.2)** | `[IMPLEMENTED]` | Multi-page visual PDF canvas viewer (`pdfjs-dist`) with synchronized zoom/rotation, normalized coordinate mapping (`NORMALIZED_0_1`), interactive OCR token bounding box overlays, schema-driven structured field inspector with PII masking, forensic findings inspector, and visual ELA heatmap raster overlays. |
| **Interactive Evidence Graph Canvas (Phase 3C)** | `[IMPLEMENTED]` | Full investigation-grade 3-region canvas at `/cases/:caseId/graph` featuring pan/zoom/minimap, 16 custom typed nodes, relationship semantic strokes and predicates, debounced autocomplete search, category and relationship status filters, 2-hop neighborhood expansion, bounded path search, and deep inspector with direct navigation to document examination. |
| **Unified Findings & Investigator Review Workbench (Phase 3D)** | `[IMPLEMENTED]` | Unified case findings triage workbench at `/cases/:caseId/findings` featuring epistemic classification preservation (`OBSERVED_FACT`, `AUTOMATED_INDICATOR`, `ANALYTICAL_INTERPRETATION`, `INVESTIGATOR_CONCLUSION`), multi-facet filtering (epistemic, severity, review status, source subsystem), deep finding inspection with heuristic confidence score caveats and coordinate provenance links, human review adjudication modal with 5 review actions (`CONFIRM_OBSERVATION`, `DISMISS_FALSE_POSITIVE`, `MARK_INCONCLUSIVE`, `REQUEST_MORE_EVIDENCE`, `MARK_NEEDS_REVIEW`) and mandatory rationale, append-only chronological review history ledger, and dossier review-readiness audit drawer with draft compilation and integrity snapshot finalization. |

---

## 7. Grounded AI Investigation Assistant

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Controlled Evidence Retrieval (`CaseEvidenceRetriever`)** | `[IMPLEMENTED]` | Deterministic case-isolated evidence retrieval compiling documents, forensic findings, consistency findings, extracted entities, relationships, evidence nodes, and investigator reviews without cross-case leakage. |
| **Strict Epistemic Classification** | `[IMPLEMENTED]` | Enforces categorical separation between Observed Facts, Automated Algorithmic Indicators, Analytical Interpretations, Contradictory Evidence, and Investigator Conclusions in all assistant outputs. |
| **Traceable Evidence Citations (`EvidenceCitation`)** | `[IMPLEMENTED]` | Every cited assertion links directly to authoritative case records (`[E-1]`, `[E-2]`) with document IDs, page numbers, coordinates, and clickable deep links to document examination and findings triage. Fabricated citations dropped automatically. |
| **Prompt Injection & Adversarial Defense** | `[IMPLEMENTED]` | Multi-layered defense: document and OCR text treated strictly as untrusted data encapsulated in explicit `<case_evidence>` XML boundaries; system prompts instruct the LLM to ignore embedded instructions, code execution, role-overrides, and tool-invocation syntax. |
| **PII Minimization & Redaction** | `[IMPLEMENTED]` | Automated runtime regex masking on bank account numbers, tax identifiers, PANs, and Aadhaar numbers prior to LLM prompt serialization. Raw unredacted PDFs never transmitted to external APIs. |
| **Pluggable LLM Provider Abstraction** | `[IMPLEMENTED]` | Protocol-driven provider layer (`LlmProviderProtocol`) supporting deterministic offline mock execution (`MockLlmProvider`) for CI/CD and self-hosted/cloud OpenAI-compatible HTTP providers (`HttpLlmProvider`) with strict timeouts and error fallbacks. |
| **Interactive Assistant Workbench (Phase 4A)** | `[IMPLEMENTED]` | Dedicated investigator interface at `/cases/:caseId/assistant` featuring conversational exploration, 6 quick-task category chips, epistemic breakdown accordions, clickable citation cards, follow-up prompt suggestions, and prominent evidentiary boundary disclosures. |
| **Deterministic Claim Grounding vs Relevance Separation (Phase 4B.1)** | `[IMPLEMENTED]` | Separates citation resolution and lexical relevance (token overlap) from semantic claim support. Claims are classified into `SUPPORTED`, `CONTRADICTED`, or `UNVERIFIED` without hallucinating entailment. |
| **Deterministic Reversal & Inversion Detection (Phase 4B.1)** | `[IMPLEMENTED]` | Detects and flags factual reversals: numerical mismatches/discrepancies, payment status flips (paid vs unpaid/overdue), candidate relationship upgrades, and document attribution errors. |
| **Independent Benchmark Negative Controls (Phase 4B.1)** | `[IMPLEMENTED]` | 7 independent negative controls validating that contradictory claims, incorrect amounts, fabricated relationships, and unsupported legal conclusions fail the grounding gate. |
| **Reasoning Manipulation Defense (Phase 4B.1)** | `[IMPLEMENTED]` | Defends against subtle reasoning manipulation attacks seeking to suppress contradictory evidence, upgrade indicators to conclusions, or treat candidate relationships as confirmed. |
| **Preservation of Legitimate Evidence Codes (Phase 4B.1)** | `[IMPLEMENTED]` | Hardened PII sanitization protects reference numbers (`INV-...`, `PO-...`, `TXN-...`, `REF-...`) and dates from false-positive destruction while sanitizing raw bank account and tax IDs. |
| **Bounded Streaming Provider Resource Limits (Phase 4B.1)** | `[IMPLEMENTED]` | Hardened `HttpLlmProvider` enforces 512KB chunked streaming limits before in-memory buffering, respects `Retry-After` headers on 429/503, fails fast without blind retries on 401/403, and strictly sanitizes credentials in error messages. |
| **Transparent Investigator Wording & Disclaimers (Phase 4B.1)** | `[IMPLEMENTED]` | Eliminated misleading "Grounded" badge in frontend UI in favor of precise "Citations Linked", "Insufficient Evidence", and explicit notice that citation resolution confirms lexical relevance rather than semantic truth. |


