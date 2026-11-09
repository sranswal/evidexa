# EVIDEXA Security Policy, Evidence Integrity & Boundary Safeguards
**Platform:** EVIDEXA — AI-Powered Digital Forensics & Document Intelligence  
**System:** Forensic Integrity & Boundary Safeguards  
**Status:** Hardened & Verified  
**Date:** November 2026

---

## 1. File Ingestion Safeguards

Documents submitted to forensic platforms frequently originate from hostile or untrusted sources. The platform enforces multi-tiered defenses before any file is saved or analyzed:

### 1.1 Content-Type vs. Magic Byte Verification
- The platform does **NOT** trust the HTTP `Content-Type` header or file extension as proof of file contents.
- During ingestion, the initial 16 bytes of the stream are inspected against known cryptographic magic byte signatures:
  - **PDF:** `%PDF-` (`0x25 0x50 0x44 0x46 0x2D`)
  - **PNG:** `\x89PNG\r\n\x1a\n` (`0x89 0x50 0x4E 0x47 0x0D 0x0A 0x1A 0x0A`)
  - **JPEG:** `\xff\xd8\xff` (`0xFF 0xD8 0xFF`)
  - **TIFF:** `II*\x00` (Little-endian) or `MM\x00*` (Big-endian)
- Uploads with mismatched signatures are immediately rejected with HTTP 400 (`SECURITY_VIOLATION`).

### 1.2 Extension Whitelist, Windows Device Names & Path Traversal Neutralization
- Only `.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, and `.tif` are allowed.
- Executable files (`.exe`, `.bat`, `.sh`, `.vbs`, `.js`) and script formats are strictly barred.
- User-supplied filenames are never treated as directory paths. `sanitize_filename()` strips all Unix `/` and Windows `\` path separators, null bytes (`0x00`), and control characters.
- **Windows Reserved Device Names:** Filenames with stems matching DOS device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) are automatically neutralized by prefixing `doc_` (e.g. `CON.pdf` $\to$ `doc_CON.pdf`), eliminating kernel thread hangs on Windows environments.
- Storage targets are dynamically validated via `ensure_safe_path()`, preventing directory traversal attacks (`../../`).

### 1.3 Atomic Streaming, Overwrite Protection & File Size Limits
- Uploads are streamed in 64 KB chunks into a uniquely tokenized temporary file in `data/temp/` (`tmp_{doc_id}_{token}.upload`).
- If the stream exceeds `MAX_UPLOAD_SIZE_BYTES` (default 50 MB), the stream is halted immediately, the partial temporary file is deleted, and an error is raised.
- **Accidental Overwrite Protection:** Before committing an upload, the storage engine verifies destination non-existence. Colliding keys raise `ConflictException` rather than overwriting existing forensic files.
- Only upon complete byte verification and SHA-256 calculation is the file atomically moved to its permanent path in `data/originals/`.
- **OS-Level Read-Only Immutability:** Immediately upon placement in `data/originals/`, files are marked read-only at the OS level (`chmod 0o444`), preventing accidental mutation.

---

## 2. Storage & Ephemeral Analysis Snapshot Architecture

### 2.1 Physical Separation of Evidence
- **`data/originals/`:** Holds original unmodified document bytes. Files are marked read-only (`0o444`) to guarantee physical evidentiary integrity.
- **`data/artifacts/`:** Stores generated forensic visualizations and intermediate analysis outputs.
- **`data/temp/`:** Ephemeral upload staging and analysis snapshot directory utilizing random cryptographic tokens to prevent collisions.

### 2.2 Ephemeral Snapshot Isolation (Byte Provenance)
To guarantee that third-party parser bugs, memory corruption, or native libraries (such as compiled `libqpdf`) can never alter the evidentiary master copy:
1. **Parser Never Receives Original Path:** The analyzer engine is never passed the path to `data/originals/`.
2. **Snapshot Generation:** An ephemeral snapshot file is generated: `data/temp/snapshot_{run_id}_{token}.pdf`.
3. **Synchronous Dual Hashing:** As the source is read and copied, source and destination SHA-256 hashes are computed simultaneously; if they do not match, snapshot creation aborts immediately.
4. **Pre-Analysis Verification:** The snapshot hash is verified to match `Document.sha256`.
5. **Execution against Snapshot:** The isolated subprocess worker executes exclusively against the snapshot file.
6. **Double Post-Analysis Immutability Verification:**
   - The snapshot hash is verified post-analysis to detect in-place writes.
   - The original stored file hash is re-verified to confirm zero file alteration.
   - If either verification fails, a `SecurityException` is raised, run is marked `FAILED` with `SNAPSHOT_IMMUTABILITY_VIOLATION` or `ORIGINAL_IMMUTABILITY_VIOLATION`, and `AuditEventType.INTEGRITY_VERIFICATION_FAILED` is recorded in the ledger.
7. **Guaranteed Cleanup:** The ephemeral snapshot is deleted in a `try ... finally` block on completion, failure, or timeout.

---

## 3. Process Isolation & Resource Boundaries

Upstream PDF analysis relies on `pikepdf`, which binds native C++ `libqpdf 12.4.2`. To isolate the FastAPI server process against memory leaks, CPU stalls, or native segfaults:

1. **Child Process Worker:** `worker.py` is invoked via `subprocess.run(shell=False)` with dedicated Python arguments.
2. **Wall-Clock Timeout Enforcement:** A supervisor-level timeout (default 30.0s) kills the subprocess if execution exceeds limits. Timeout raises `subprocess.TimeoutExpired` and transitions the run to `FAILED` with `error_code="ANALYSIS_TIMEOUT"`.
3. **Bounded Buffers:** Subprocess stdout is truncated to 1 MB and stderr to 64 KB.
4. **Bounded Output Collections:** Findings emitted by the worker are strictly capped at 500 observations with a truncation marker (`system.truncated`).
5. **Path Sanitization:** File system paths are redacted in worker output to prevent host directory leakage.
6. **Stale Run Recovery:** If the application terminates abnormally while a processing run is in progress, lifespan startup identifies orphaned `RUNNING` records, marks them `FAILED` with `error_code="RUN_INTERRUPTED"`, and records `AuditEventType.PROCESSING_RUN_INTERRUPTED`.

---

## 4. Evidence Provenance & Local Tamper-Evident Ledger

### 4.1 SHA-256 Hash Chaining
- Each audit event seals the hash of the preceding event (`previous_event_hash`) and computes `event_hash = SHA256(canonical_json(event_payload))`.
- All forensic lifecycle milestones are permanently recorded:
  - `CASE_CREATED`, `CASE_STATUS_CHANGED`
  - `DOCUMENT_INGESTED`, `FILE_HASH_REGISTERED`
  - `ANALYSIS_REQUESTED`, `PROCESSING_RUN_STARTED`, `PROCESSING_RUN_COMPLETED`
  - `INTEGRITY_VERIFICATION_FAILED`, `PROCESSING_RUN_INTERRUPTED`

### 4.2 Independent Head Checkpointing
- To detect deletion or truncation of the latest event(s) (tail-truncation attacks), `audit_checkpoints` stores `head_event_hash` and `event_count` transactionally.
- Chain verification traverses from genesis event 1 to head checkpoint, guaranteeing chronological continuity.

### 4.3 Case Archival & Non-Destructive Retention
- No physical deletion endpoint (`DELETE /cases/{id}`) is exposed.
- Cases are soft-archived via `POST /cases/{id}/archive`, setting `CaseStatus.ARCHIVED`.
- Once archived:
  - New document ingestion is strictly rejected (`ValidationException`).
  - New forensic analysis execution is strictly rejected (`ValidationException`).
  - All existing documents, evidence nodes, forensic findings, processing runs, and audit ledger entries remain permanently accessible for review.

---

## 5. Security Status & Realistic Boundaries

To maintain technical accuracy, the platform avoids inflated claims:
- **Audit Ledger:** Is a *local tamper-evident audit ledger with SHA-256 chaining and head checkpointing*. It is not a distributed blockchain or independently anchored witness network.
- **Process Worker:** Is a *process-isolated subprocess worker with timeout enforcement and bounded I/O*. It is not a hardware-isolated microVM or seccomp sandbox.
- **Multi-Tenancy:** Case boundaries and document ownership are strictly enforced via relational foreign keys and ID checks. Full end-user authentication (OAuth2 / JWT) and enterprise RBAC remain scheduled for future deployment phases.
