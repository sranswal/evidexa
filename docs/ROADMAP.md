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
│   [COMPLETED]   │     │   [COMPLETED]   │     │  [IN PROGRESS]  │     │    [PLANNED]    │
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
- [x] Schema-driven structured extraction for invoices, receipts, and bank statements.
- [x] Exact financial decimal quantization (currency minor units) eliminating floating-point rounding errors.
- [x] Zero plaintext PII persistence (automatic masking of bank accounts, PANs, Aadhaar numbers).
- [x] Deterministic entity resolution across documents (`ORGANIZATION`, `PERSON`, `TAX_ID`, `ACCOUNT`, `AMOUNT`).
- [x] Relationship Ontology V2: directed Subject-Predicate-Object semantics with explicit status vs. score separation.
- [x] Separation of discrete invoice billing events (`INVOICED`) from contractual supply arrangements (`SUPPLIES`).
- [x] Contradiction persistence preserving conflicting evidence signals under manual investigator review.
- [x] Database migration `006_relationship_semantics` with full backward compatibility and rollback verification.

### Phase 3: Investigation Workspace, Interactive Graph & Dossier Generator `[IN PROGRESS]`
- [ ] Interactive Web UI investigation workspace (React / Tailwind / Canvas).
- [ ] Visual multi-page document viewer with synchronized forensic heatmap overlays (ELA / DCT).
- [ ] Interactive node-and-edge Evidence Graph explorer with filterable relationship predicates.
- [ ] Human review workbench for matching entities and confirming candidate relationships with mandatory audit reasons.
- [ ] Exportable court-defensible investigation dossiers in structured PDF and cryptographically signed JSON formats.
- [ ] Batch document upload queue with real-time processing progress indicators.

### Phase 4: Enterprise Scale, Ring Detection & Multimodal Intelligence `[PLANNED]`
- [ ] Multi-case applicant correlation and fraud ring detection using privacy-preserving graph anonymization.
- [ ] Multilingual OCR expansion supporting Devanagari, Arabic, and CJK document scripts.
- [ ] Enterprise identity integration: OpenID Connect (OIDC), SAML 2.0, and role-based access control (RBAC).
- [ ] High-throughput distributed Celery / Redis task workers for large-scale enterprise batch ingestion.
- [ ] Hardware-accelerated inference profiles (NVIDIA TensorRT / OpenVINO) for high-density document scanning.

