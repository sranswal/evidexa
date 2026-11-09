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

## 4. Evidence Intelligence & Provenance Graph

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Unified Evidence Graph Nodes** | `[IMPLEMENTED]` | Links cases, documents, pages, OCR tokens, forensic observations, fields, entities, and relationships. |
| **Sub-Document Provenance** | `[IMPLEMENTED]` | Every finding and field value links to source document ID, page index, normalized bounding box, and token IDs. |
| **Contradiction Persistence** | `[IMPLEMENTED]` | Pre-existing contradictory evidence signals remain completely visible in evidence payloads even after manual human review confirmation. |
| **Hash-Chained Audit Ledger** | `[IMPLEMENTED]` | Tamper-evident audit log with SHA-256 hash chaining and sequence verification for all operational and review events. |
| **Artifact Storage Verification** | `[IMPLEMENTED]` | Serialized analysis and relationship artifacts verified via synchronous SHA-256 recalculation upon retrieval. |
| **Interactive Graph Visualization** | `[IN PROGRESS]` | Visual node-and-edge investigation canvas in web UI (see Phase 3 roadmap). |

---

## 5. Investigation Workspace & Reporting

| Capability | Status | Description & Engineering Details |
|---|:---:|---|
| **Case Management & Isolation** | `[IMPLEMENTED]` | Case creation, listing, status updates, and soft archival (`CaseStatus.ARCHIVED`) with strict single-case isolation. |
| **Single-Case 404 Security Barrier** | `[IMPLEMENTED]` | Cross-case entity or relationship access attempts raise `SecurityException` and return HTTP 404. |
| **Human Match & Relationship Review** | `[IMPLEMENTED]` | Dedicated REST review endpoints with mandatory reviewer ID, timestamp, and audit trail generation. |
| **REST API OpenAPI Specification** | `[IMPLEMENTED]` | Comprehensive Swagger UI (`/docs`) and ReDoc (`/redoc`) documentation covering all case, forensic, OCR, and relationship routes. |
| **Defensible Investigation Dossier Export**| `[IN PROGRESS]` | PDF and cryptographically signed JSON dossier export combining findings, evidence nodes, and human review history. |
| **Web UI Investigation Workspace** | `[IN PROGRESS]` | Frontend investigation dashboard for visual document inspection and graph exploration. |

