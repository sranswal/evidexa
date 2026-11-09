# Changelog

All notable changes to the **EVIDEXA** platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] - 2026-11-09

### Added
- **Official Brand Identity:** Transitioned product branding to **EVIDEXA** (*Intelligence Behind Every Evidence*).
- **Relationship Ontology V2:** Standardized directed Subject-Predicate-Object semantics (`ISSUED`, `BILLED_TO`, `INVOICED`, `HELD_BY`, `SUPPLIES`, `REPRESENTS`, `DUPLICATE_OF`).
- **Commercial Invariant Protection:** Separated single invoice billing events (`INVOICED`) from long-term ongoing contractual supply agreements (`SUPPLIES`).
- **Status vs. Score Separation:** Decoupled formal status determination (`EVIDENTIARY_RULE` vs `HUMAN_REVIEW`) from heuristic ranking weights.
- **Duplicate Categorization:** Introduced `DuplicateKind` distinguishing `BYTE_IDENTICAL`, `VISUALLY_SIMILAR`, and `SEMANTICALLY_SIMILAR`.
- **Contradiction Persistence:** Enforced permanent visibility of contradicting evidence signals in evidence payloads even following human review confirmation.
- **Database Migration 006:** Added `006_relationship_semantics` with full bidirectional schema and data migration for legacy relationships.
- **Cross-Document Entity Resolution:** Deterministic cross-document matching for organizations, persons, tax identifiers, bank accounts, and currency amounts.
- **Document Understanding Layer:** Hybrid adaptive OCR routing between PDFium (vector text) and RapidOCR (ONNX scanned text) with normalized coordinate mapping (`NORMALIZED_0_1`).
- **Financial Precision & PII Protection:** Decimal quantization according to currency minor units and zero-plaintext masking for sensitive accounts.
- **Visual Forensic Analysis:** Error Level Analysis (ELA) and 2D-DCT copy-move forgery detection.
- **Structural PDF Analysis:** Subprocess-isolated PDF structural analysis worker (`worker.py`) detecting incremental updates and font stream anomalies.
- **Ephemeral Snapshot Lifecycle:** Double SHA-256 pre/post-analysis file immutability verification.
- **Cryptographic Audit Ledger:** SHA-256 hash-chained append-only event ledger with sequence verification.
- **Case Management & Isolation:** Case lifecycle management with soft archival and 404 security barriers.
- **Automated Verification:** Comprehensive test suite of 309 passing tests with 100% pass rate.

