# REST API Specification (v1)
**Project:** Enterprise Document Forensics & Contextual Intelligence Platform  
**Base URL:** `http://localhost:8000/api/v1`  
**OpenAPI Interactive Docs:** `http://localhost:8000/docs`  
**Date:** November 2026

---

## 1. Standard Error Envelope

All error responses strictly follow a uniform JSON structure inspired by RFC 7807:

```json
{
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "Case with ID '8a2b3c4d-...' not found.",
    "details": {
      "entity_type": "Case",
      "entity_id": "8a2b3c4d-..."
    }
  }
}
```

### Standard Error Codes
- `ENTITY_NOT_FOUND` (404): Resource does not exist.
- `SECURITY_VIOLATION` (400): File signature mismatch, unsupported extension, or path traversal.
- `VALIDATION_ERROR` (422): Domain business invariant violation.
- `REQUEST_VALIDATION_ERROR` (422): Invalid request schema/types.
- `INVALID_STATUS_TRANSITION` (422): Unpermitted lifecycle state change.
- `CONFLICT_ERROR` (409): Unique constraint violation.
- `STORAGE_ERROR` (500): Filesystem I/O failure.
- `INTERNAL_SERVER_ERROR` (500): Unhandled exception.

---

## 2. Endpoints Summary

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Application health and version check |
| `GET` | `/api/v1/health` | Versioned API health check |
| `POST` | `/api/v1/cases` | Create a new investigation workspace |
| `GET` | `/api/v1/cases` | List cases with pagination and status filter |
| `GET` | `/api/v1/cases/{case_id}` | Retrieve specific case details |
| `POST` | `/api/v1/cases/{case_id}/documents` | Safely upload and register an original document |
| `GET` | `/api/v1/cases/{case_id}/documents` | List documents registered in a case |
| `GET` | `/api/v1/cases/{case_id}/findings` | Retrieve forensic findings for a case |
| `GET` | `/api/v1/cases/{case_id}/audit-events` | Retrieve immutable audit ledger events |
| `GET` | `/api/v1/cases/{case_id}/audit-events/verify` | Verify cryptographic hash chain integrity |
| `POST` | `/api/v1/cases/{case_id}/documents/{document_id}/classification` | Run multi-class document & page classification |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/classification` | Get latest classification result and candidates |
| `POST` | `/api/v1/cases/{case_id}/documents/{document_id}/classification/override` | Record human review classification override |
| `POST` | `/api/v1/cases/{case_id}/documents/{document_id}/extraction` | Extract structured fields against schema |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/extraction` | Get latest structured extraction result |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/extraction/schemas` | List registered extraction schemas |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/extraction/schemas/{schema_id}` | Get schema definition and field details |

---

## 3. Endpoint Details & Examples

### 3.1 Create Case
- **Endpoint:** `POST /api/v1/cases`
- **Request:**
  ```json
  {
    "title": "Corporate Loan Application - Acme Corp",
    "description": "Suspected forged salary slips and altered bank statement",
    "created_by": "underwriter_99",
    "metadata": {
      "application_id": "APP-2026-981"
    }
  }
  ```
- **Response (`201 Created`):**
  ```json
  {
    "id": "e6f42a59-5431-4a11-82d2-8b6fa39f5507",
    "case_reference": "CASE-20261107-1E8A",
    "title": "Corporate Loan Application - Acme Corp",
    "description": "Suspected forged salary slips and altered bank statement",
    "status": "DRAFT",
    "created_at": "2026-11-07T09:15:00.000000+00:00",
    "updated_at": "2026-11-07T09:15:00.000000+00:00",
    "created_by": "underwriter_99",
    "metadata": {
      "application_id": "APP-2026-981"
    }
  }
  ```

---

### 3.2 List Cases
- **Endpoint:** `GET /api/v1/cases?skip=0&limit=50&status=DRAFT`
- **Response (`200 OK`):**
  ```json
  {
    "items": [
      {
        "id": "e6f42a59-5431-4a11-82d2-8b6fa39f5507",
        "case_reference": "CASE-20261107-1E8A",
        "title": "Corporate Loan Application - Acme Corp",
        "status": "DRAFT",
        "created_at": "2026-11-07T09:15:00.000000+00:00",
        "updated_at": "2026-11-07T09:15:00.000000+00:00",
        "created_by": "underwriter_99",
        "metadata": {}
      }
    ],
    "total": 1,
    "skip": 0,
    "limit": 50
  }
  ```

---

### 3.3 Upload Document
- **Endpoint:** `POST /api/v1/cases/{case_id}/documents`
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `file`: Binary file stream (PDF, PNG, JPEG, TIFF).
  - `created_by`: (Optional) Investigator identifier string.
- **Response (`201 Created`):**
  ```json
  {
    "id": "7a3f8b1c-9922-4ef1-b5f3-4e8c1a329d77",
    "case_id": "e6f42a59-5431-4a11-82d2-8b6fa39f5507",
    "original_filename": "bank_statement_august.pdf",
    "media_type": "application/pdf",
    "file_extension": ".pdf",
    "file_size_bytes": 245192,
    "sha256": "4b5d2c88f391e3e8d91a782bcf52a8192a543990b79ce8f918bbca2843efc912",
    "storage_key": "e6f42a59-5431-4a11-82d2-8b6fa39f5507/7a3f8b1c-9922-4ef1-b5f3-4e8c1a329d77.pdf",
    "page_count": null,
    "document_type": "UNKNOWN",
    "ingestion_status": "STORED",
    "created_at": "2026-11-07T09:16:30.000000+00:00",
    "created_by": "underwriter_99",
    "metadata": {}
  }
  ```

---

### 3.4 List Findings
- **Endpoint:** `GET /api/v1/cases/{case_id}/findings`
- **Response (`200 OK`):**
  ```json
  {
    "items": [],
    "total": 0,
    "skip": 0,
    "limit": 50
  }
  ```
  *(Returns an authentic empty collection until future processing runs execute).*

---

### 3.5 Verify Audit Chain Integrity
- **Endpoint:** `GET /api/v1/cases/{case_id}/audit-events/verify`
- **Response (`200 OK`):**
  ```json
  {
    "case_id": "e6f42a59-5431-4a11-82d2-8b6fa39f5507",
    "chain_valid": true,
    "total_events": 3,
    "error_message": null
  }
  ```

---

### 3.6 Document Classification & Reviewer Override
- **Endpoint:** `POST /api/v1/cases/{case_id}/documents/{document_id}/classification`
- **Response (`200 OK`):**
  ```json
  {
    "document_id": "7a3f8b1c-9922-4ef1-b5f3-4e8c1a329d77",
    "processing_run_id": "cad4191a-2fa7-492b-9909-143cd796ba96",
    "predicted_class": "INVOICE",
    "effective_class": "INVOICE",
    "ranking_score": 0.85,
    "score_type": "rule_ranking_score",
    "classification_method": "rule_pattern_classifier_v1",
    "candidates": [
      {
        "document_class": "INVOICE",
        "ranking_score": 0.85,
        "matched_signals": ["pattern_tax_invoice", "pattern_due_date", "pattern_bill_to"]
      }
    ],
    "page_classifications": [
      {
        "page_number": 1,
        "predicted_class": "INVOICE",
        "ranking_score": 0.85,
        "candidates": [],
        "matched_signals": ["pattern_tax_invoice"]
      }
    ],
    "manual_override": null,
    "evaluated_at": "2026-11-09T10:00:00Z"
  }
  ```

- **Reviewer Override Endpoint:** `POST /api/v1/cases/{case_id}/documents/{document_id}/classification/override`
- **Payload:**
  ```json
  {
    "target_class": "CONTRACT",
    "reason": "Document contains formal master service agreement addendum.",
    "overridden_by": "asserted-investigator-01"
  }
  ```
  *(Note: `overridden_by` represents an asserted reviewer identifier in unauthenticated development mode. The original `predicted_class` is preserved and recorded to the local append-only hash-chained audit ledger).*

---

### 3.7 Structured Field Extraction
- **Endpoint:** `POST /api/v1/cases/{case_id}/documents/{document_id}/extraction`
- **Payload:**
  ```json
  {
    "schema_id": "invoice_v1",
    "options": {
      "page_number": 1
    }
  }
  ```
  *(If `schema_id` is omitted, the schema is auto-resolved from the document's effective classification. For mixed-document extraction across multiple pages, `options.page_number` allows targeted extraction per page).*
- **Evidentiary Guarantees:**
  - **Financial Precision:** All monetary amounts are exact Python `Decimal` values quantized by currency minor unit rules (e.g. 2 for USD, 0 for JPY, 3 for KWD).
  - **Zero Plaintext PII Leakage:** Sensitive account numbers are masked immediately (`****{last4}`); unmasked plaintext never appears in raw text, candidates, evidence nodes, or extraction artifacts.
  - **Ambiguity Preservation:** Numeric dates with ambiguous ordering or ambiguous currency symbols (`$`, `¥`) evaluate to `None` with candidate interpretations and explicit validation warnings unless clarified by document context.
  - **Provenance:** Every extracted field links to an `EvidenceNode` (`EXTRACTED_FIELD`) with exact top-left normalized bounding boxes (`NORMALIZED_0_1`) and supporting OCR token IDs. Fabricated coordinates are strictly prohibited.
  - **Rerun Isolation & Artifact Integrity:** Every extraction run creates an independent `ProcessingRun` and separate storage artifact file with SHA-256 verification upon retrieval.

---

### 3.8 Cross-Document Entity Resolution
- **Trigger Resolution:** `POST /api/v1/cases/{case_id}/entity-resolution`
  - Body: `{"options": {}, "mentions": [...]}` (or omit `mentions` to auto-harvest from completed extractions).
  - Status: `201 Created`
  - Response: Full `EntityResolutionResult` containing `candidate_matches`, `resolved_entities`, `unresolved_mentions`, and execution metrics.
- **List Runs:** `GET /api/v1/cases/{case_id}/entity-resolution/runs`
  - Status: `200 OK`
  - Returns array of `EntityResolutionRunSummary`.
- **Get Run Result:** `GET /api/v1/cases/{case_id}/entity-resolution/runs/{run_id}`
  - Status: `200 OK`
  - Returns full `EntityResolutionResult` with SHA-256 integrity verification.
- **Get Latest Result:** `GET /api/v1/cases/{case_id}/entity-resolution/latest`
  - Status: `200 OK`
- **List Resolved Entities:** `GET /api/v1/cases/{case_id}/entity-resolution/entities?skip=0&limit=50`
  - Status: `200 OK`
  - Returns paginated `{"items": [...], "total": N, "skip": 0, "limit": 50}`.
- **List Candidate Matches:** `GET /api/v1/cases/{case_id}/entity-resolution/matches?entity_type=ORGANIZATION&decision_status=ALGORITHMIC_CANDIDATE&skip=0&limit=50`
  - Status: `200 OK`
  - Returns paginated `{"items": [...], "total": N, "skip": 0, "limit": 50}`.
- **Get Match Details:** `GET /api/v1/cases/{case_id}/entity-resolution/matches/{match_id}`
  - Status: `200 OK`
  - Returns single `EntityCandidateMatch` with evidence signals and full review history.
- **Submit Human Review Decision:** `POST /api/v1/cases/{case_id}/entity-resolution/matches/{match_id}/review`
  - Payload:
    ```json
    {
      "decision": "CONFIRM_MATCH",
      "reason": "Corroborated by shared laboratory security clearance badge ID in supplementary file.",
      "reviewer_id": "asserted-investigator-01"
    }
    ```
  - Status: `200 OK`
  - Returns updated `EntityCandidateMatch` and records `ENTITY_MATCH_REVIEWED` to the hash-chained audit ledger.
- **List Match Reviews:** `GET /api/v1/cases/{case_id}/entity-resolution/matches/{match_id}/reviews`
  - Status: `200 OK`
  - Returns array of historical `HumanMatchReview` records.

---

### 3.9 Cross-Document Relationship Detection & Ontology V2
- **Detect Relationships:** `POST /api/v1/cases/{case_id}/relationships/detect`
  - Status: `201 Created`
  - Response: Full `RelationshipDetectionResult` with `run` summary metrics (`confirmed_count`, `candidate_count`, `contradicted_count`, `unresolved_count`, `rejected_count`, `execution_time_ms`, `storage_path`, `storage_sha256`) and list of `relationships` adhering to Ontology V2.
- **List Detection Runs:** `GET /api/v1/cases/{case_id}/relationships/runs`
  - Status: `200 OK`
  - Returns array of `RelationshipDetectionRun` records.
- **Get Latest Result:** `GET /api/v1/cases/{case_id}/relationships/latest`
  - Status: `200 OK`
  - Returns the most recent `RelationshipDetectionResult` for the case.
- **Get Run Result by ID:** `GET /api/v1/cases/{case_id}/relationships/runs/{run_id}`
  - Status: `200 OK`
  - Returns `RelationshipDetectionResult` reconstructed from SHA-256 verified JSON artifact.
- **Query Relationships (Paginated & Filtered):** `GET /api/v1/cases/{case_id}/relationships/?relationship_type=ISSUED&status=CONFIRMED&skip=0&limit=50`
  - Query parameters:
    - `relationship_type`: Optional enum filter (`RelationshipType`, including `ISSUED`, `BILLED_TO`, `INVOICED`, `HELD_BY`, `SUPPLIES`, `REPRESENTS`, `DUPLICATE_OF`, etc., and legacy aliases).
    - `status`: Optional enum filter (`RelationshipStatus`: `CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`, `REJECTED`).
    - `source_document_id`, `target_document_id`: Optional document UUID filters.
    - `source_entity_id`, `target_entity_id`: Optional entity UUID filters.
    - `skip`: Integer pagination offset (default: 0).
    - `limit`: Integer pagination limit (default: 50, max: 200).
  - Status: `200 OK`
  - Response: `{"items": [...], "total": N, "skip": 0, "limit": 50, "ontology_version": "2.0"}`.
- **Get Relationship Details:** `GET /api/v1/cases/{case_id}/relationships/{relationship_id}`
  - Status: `200 OK`
  - Returns full `DetectedRelationship` with:
    - `ontology_version`: `"2.0"`
    - `status_determination_method`: `"EVIDENTIARY_RULE"` or `"HUMAN_REVIEW"`
    - `status_rationale`: Deterministic reasoning or reviewer justification
    - `duplicate_kind`: `"BYTE_IDENTICAL"`, `"VISUALLY_SIMILAR"`, `"SEMANTICALLY_SIMILAR"`, `"UNRESOLVED_DUPLICATE_CANDIDATE"` (when applicable)
    - `evidence`: (`detection_method`, `confidence_score`, `supporting_signals`, `contradicting_signals`, `detector_name`)
    - `review_history`: List of `RelationshipReviewRecord` entries
- **Submit Human Review Decision:** `POST /api/v1/cases/{case_id}/relationships/{relationship_id}/review`
  - Payload:
    ```json
    {
      "decision": "CONFIRM_RELATIONSHIP",
      "reason": "Verified purchase order number cross-referenced against ERP log.",
      "reviewer_id": "auditor-42"
    }
    ```
  - Decisions: `CONFIRM_RELATIONSHIP`, `REJECT_RELATIONSHIP`, `MARK_UNRESOLVED`.
  - Status: `200 OK`
  - Evidentiary Semantics:
    - Sets `status_determination_method` to `HUMAN_REVIEW`.
    - Preserves all pre-existing contradictory evidence signals in the evidence payload.
    - Appends `RELATIONSHIP_REVIEWED` to the hash-chained audit ledger.
- **List Relationship Reviews:** `GET /api/v1/cases/{case_id}/relationships/{relationship_id}/reviews`
  - Status: `200 OK`
  - Returns array of `RelationshipReviewRecord` objects ordered by review date.
  - Returns updated `DetectedRelationship` and appends `RELATIONSHIP_REVIEWED` to the hash-chained audit ledger.
- **List Relationship Reviews:** `GET /api/v1/cases/{case_id}/relationships/{relationship_id}/reviews`
  - Status: `200 OK`
  - Returns array of `RelationshipReviewRecord` objects ordered by review date.


