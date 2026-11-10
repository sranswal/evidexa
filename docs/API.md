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
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}` | Retrieve detailed metadata for a registered document |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/download` | Download or stream original verified evidence file |
| `GET` | `/api/v1/cases/{case_id}/documents/{document_id}/artifacts/{run_id}/{filename}` | Stream or download derived forensic artifact |
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
| `POST` | `/api/v1/cases/{case_id}/consistency/analyze` | Trigger cross-document consistency analysis |
| `GET` | `/api/v1/cases/{case_id}/consistency/runs` | List consistency analysis runs for a case |
| `GET` | `/api/v1/cases/{case_id}/consistency/runs/{run_id}` | Retrieve specific consistency run metadata |
| `GET` | `/api/v1/cases/{case_id}/consistency/findings` | List cross-document consistency findings with filters |
| `GET` | `/api/v1/cases/{case_id}/consistency/findings/{finding_id}` | Retrieve specific finding details, fields, and locations |
| `POST` | `/api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews` | Record human review decision on a finding |
| `GET` | `/api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews` | List chronological human review audit history |
| `POST` | `/api/v1/cases/{case_id}/assistant/query` | Submit evidence-grounded question to AI assistant |
| `GET` | `/api/v1/cases/{case_id}/assistant/context-summary` | Retrieve available evidentiary counts for assistant |

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

### 3.4 Retrieve Forensic Artifact
- **Endpoint:** `GET /api/v1/cases/{case_id}/documents/{document_id}/artifacts/{run_id}/{filename}`
- **Security & Scope:** Validates case and document ownership. Sanitizes filename against directory traversal (`sanitize_filename`). Never exposes absolute host filesystem paths.
- **Media Types:** `image/png`, `image/jpeg`, `application/json`, or `application/octet-stream`.
- **Response (`200 OK`):** Stream of authentic derived forensic artifact bytes (e.g. ELA heatmap raster or extraction output).

---

### 3.5 List Findings
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

---

## 10. Cross-Document Consistency Analysis Engine

Deterministic cross-document consistency checks evaluate whether documents belonging to the same case contradict each other, exhibit discrepancies, or demonstrate coherent commercial alignment.

### 10.1 Trigger Consistency Analysis
- **Endpoint:** `POST /api/v1/cases/{case_id}/consistency/analyze`
- **Status:** `201 Created`
- **Request Body (Optional):**
  ```json
  {
    "document_ids": ["doc-uuid-1", "doc-uuid-2"],
    "rule_ids": ["invoice_receipt_total_consistency", "po_invoice_financials_consistency"],
    "monetary_tolerance": "0.00",
    "parameters": {
      "transactions": []
    }
  }
  ```
- **Response Model (`ConsistencyAnalysisResult`):**
  ```json
  {
    "case_id": "8a2b3c4d-...",
    "analysis_run_id": "run-uuid-...",
    "status": "SUCCEEDED",
    "findings": [
      {
        "id": "finding-uuid-...",
        "case_id": "8a2b3c4d-...",
        "analysis_run_id": "run-uuid-...",
        "rule_id": "invoice_receipt_total_consistency",
        "rule_version": "1.0.0",
        "category": "FINANCIAL_VALIDATION",
        "title": "Invoice vs Receipt Total: INCONSISTENT",
        "explanation": "Monetary discrepancy detected: Invoice 'inv.pdf' has 85000.00 INR whereas Receipt 'rcpt.pdf' has 95000.00 INR (difference of 10000.00 INR).",
        "severity": "HIGH",
        "outcome": "INCONSISTENT",
        "score": 1.0,
        "score_semantics": "rule_deterministic_confidence",
        "affected_document_ids": ["doc-1", "doc-2"],
        "compared_fields": ["total_amount", "currency"],
        "original_values": {
          "doc-1:total_amount": "85,000.00",
          "doc-2:total_amount": "95,000.00"
        },
        "normalized_values": {
          "doc-1:total_amount": "85000.00",
          "doc-2:total_amount": "95000.00"
        },
        "locations": [
          {
            "document_id": "doc-1",
            "field_key": "total_amount",
            "page_number": 1,
            "bounding_box": {"x": 0.65, "y": 0.82, "width": 0.25, "height": 0.04},
            "evidence_node_id": "ev-doc-1-total_amount"
          }
        ],
        "detection_method": "MONETARY_RECONCILIATION_CHECK",
        "rule_parameters": {"monetary_tolerance": "0.00"},
        "limitations": [
          "Total amount matching does not prove settlement without verified payment ledger confirmation.",
          "Discrepancies may reflect partial payments, surcharges, or discounts."
        ],
        "status": "DETECTED",
        "review_status": "UNREVIEWED",
        "is_human_reviewed": false
      }
    ],
    "total_findings": 1,
    "outcomes_summary": {"INCONSISTENT": 1},
    "rules_applied": ["invoice_receipt_total_consistency"],
    "duration_ms": 14.5,
    "storage_artifact_key": "cases/case-id/consistency/run-id/consistency_analysis_run-id.json",
    "storage_artifact_sha256": "4a7b..."
  }
  ```

### 10.2 List Consistency Analysis Runs
- **Endpoint:** `GET /api/v1/cases/{case_id}/consistency/runs`
- **Status:** `200 OK`
- **Response:** Array of `ProcessingRun` objects.

### 10.3 Retrieve Consistency Run Details
- **Endpoint:** `GET /api/v1/cases/{case_id}/consistency/runs/{run_id}`
- **Status:** `200 OK`
- **Response:** Single `ProcessingRun` object.

### 10.4 List Consistency Findings
- **Endpoint:** `GET /api/v1/cases/{case_id}/consistency/findings`
- **Query Parameters:**
  - `run_id`: Filter by analysis run UUID.
  - `rule_id`: Filter by rule machine identifier.
  - `outcome`: Filter by outcome (`CONSISTENT`, `INCONSISTENT`, `POTENTIAL_ANOMALY`, `INSUFFICIENT_EVIDENCE`, `NOT_APPLICABLE`).
  - `status`: Filter by finding status (`DETECTED`, `CONFIRMED_OBSERVATION`, `DISMISSED`, `RESOLVED`, `NEEDS_REVIEW`).
  - `document_id`: Filter by affected document UUID.
  - `limit`: Integer (default: 50, max: 500).
  - `offset`: Integer (default: 0).
- **Status:** `200 OK`
- **Response:** `{"findings": [...], "total": N, "limit": 50, "offset": 0}`.

### 10.5 Retrieve Individual Consistency Finding
- **Endpoint:** `GET /api/v1/cases/{case_id}/consistency/findings/{finding_id}`
- **Status:** `200 OK`
- **Response:** Full `ConsistencyFinding` object with complete evidence locations and review history.

### 10.6 Submit Human Review Decision
- **Endpoint:** `POST /api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews`
- **Status:** `201 Created`
- **Request Body:**
  ```json
  {
    "decision": "CONFIRM_INCONSISTENCY",
    "reviewer_id": "investigator-alice",
    "reason": "Confirmed physical invoice shows distinct amount from point-of-sale receipt."
  }
  ```
- **Allowed Actions:**
  - `CONFIRM_INCONSISTENCY` -> Transitions finding status to `CONFIRMED_OBSERVATION`.
  - `DISMISS` -> Transitions finding status to `DISMISSED`.
  - `MARK_INSUFFICIENT_EVIDENCE` -> Transitions finding status to `RESOLVED`.
  - `REQUEST_MORE_EVIDENCE` -> Transitions finding status to `NEEDS_REVIEW`.
- **Response:** Updated `ConsistencyFinding` object with updated `status`, `review_status`, and `review_history`.

### 10.7 Retrieve Finding Review History
- **Endpoint:** `GET /api/v1/cases/{case_id}/consistency/findings/{finding_id}/reviews`
- **Status:** `200 OK`
- **Response:** Chronological array of `ConsistencyReview` records preserving asserted reviewer IDs, timestamps, and justifications.

---

## 11. Unified Evidence Graph Endpoints

The Evidence Graph query layer projects authoritative relational records (cases, documents, evidence nodes, forensic findings, consistency findings, relationships, and entity candidate matches) as a single connected in-memory model.

### 11.1 Retrieve Case Evidence Graph
- **Endpoint:** `GET /api/v1/cases/{case_id}/graph`
- **Query Parameters:**
  - `node_types`: Array of strings (e.g. `DOCUMENT`, `EVIDENCE`, `FORENSIC_FINDING`, `CONSISTENCY_FINDING`, `ORGANIZATION`, `INVOICE`).
  - `relationship_types`: Array of strings (e.g. `ISSUED`, `INVOICED`, `HAS_EVIDENCE`, `SUPPORTED_BY`, `REFERENCES_PURCHASE_ORDER`).
  - `statuses`: Array of strings (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`, `REJECTED`).
  - `document_ids`: Array of document UUIDs.
  - `limit`: Integer (default: 500, max: 2000).
  - `offset`: Integer (default: 0).
- **Status:** `200 OK`
- **Response:**
  ```json
  {
    "case_id": "case-uuid",
    "nodes": [
      {
        "id": "node-uuid",
        "case_id": "case-uuid",
        "node_type": "DOCUMENT",
        "source_entity_type": "Document",
        "source_entity_id": "doc-uuid",
        "label": "invoice_101.pdf",
        "display_attributes": {
          "filename": "invoice_101.pdf",
          "document_type": "INVOICE",
          "sha256": "4a7b..."
        },
        "provenance": {"storage_key": "cases/case-uuid/invoice_101.pdf"},
        "created_at": "2026-11-09T12:00:00Z"
      }
    ],
    "edges": [
      {
        "id": "edge-uuid",
        "case_id": "case-uuid",
        "source_node_id": "node-uuid-a",
        "target_node_id": "node-uuid-b",
        "predicate": "REFERENCES_PURCHASE_ORDER",
        "status": "CONFIRMED",
        "status_determination_method": "EVIDENTIARY_RULE",
        "score": 0.98,
        "supporting_evidence_ids": ["ev-1"],
        "contradicting_evidence_ids": [],
        "source_relationship_id": "rel-uuid",
        "explanation": "Invoice field po_number explicitly cites PO-50",
        "metadata": {}
      }
    ],
    "total_nodes": 12,
    "total_edges": 15,
    "truncated": false,
    "query_metadata": {
      "limit": 500,
      "offset": 0
    },
    "projection_version": "1.0.0"
  }
  ```

### 11.2 Retrieve Graph Node Details & Degree
- **Endpoint:** `GET /api/v1/cases/{case_id}/graph/nodes/{node_id}`
- **Status:** `200 OK`
- **Response:**
  ```json
  {
    "node": {
      "id": "node-uuid",
      "case_id": "case-uuid",
      "node_type": "DOCUMENT",
      "source_entity_type": "Document",
      "source_entity_id": "doc-uuid",
      "label": "invoice_101.pdf",
      "display_attributes": {},
      "provenance": {},
      "created_at": "2026-11-09T12:00:00Z"
    },
    "outgoing_edges": [...],
    "incoming_edges": [...],
    "degree": 4
  }
  ```

### 11.3 Retrieve Bounded k-hop Neighborhood
- **Endpoint:** `GET /api/v1/cases/{case_id}/graph/nodes/{node_id}/neighbors`
- **Query Parameters:**
  - `max_hops`: Integer (default: 2, min: 1, max: 5).
  - `limit`: Integer (default: 200, max: 1000).
  - `relationship_types`: Array of strings.
  - `statuses`: Array of strings.
- **Status:** `200 OK`
- **Response:**
  ```json
  {
    "case_id": "case-uuid",
    "center_node_id": "node-uuid",
    "hops": 2,
    "nodes": [...],
    "edges": [...],
    "total_nodes": 8,
    "total_edges": 9,
    "truncated": false
  }
  ```

### 11.4 Search Directed Evidentiary Paths
- **Endpoint:** `GET /api/v1/cases/{case_id}/graph/paths`
- **Query Parameters:**
  - `source_node_id`: Starting node UUID (required).
  - `target_node_id`: Target destination node UUID (required).
  - `max_depth`: Integer (default: 4, min: 1, max: 6).
  - `max_paths`: Integer (default: 10, min: 1, max: 50).
  - `confirmed_only`: Boolean (default: `false`). When `true`, restricts path traversal to edges with status `CONFIRMED`.
  - `relationship_types`: Array of strings.
- **Status:** `200 OK`
- **Response:**
  ```json
  {
    "case_id": "case-uuid",
    "source_node_id": "node-uuid-src",
    "target_node_id": "node-uuid-tgt",
    "max_depth": 4,
    "paths": [
      {
        "nodes": [...],
        "edges": [...],
        "length": 2,
        "is_confirmed_only": true
      }
    ],
    "total_paths_found": 1,
    "truncated": false
  }
  ```

---

## 12. Findings Aggregation & Evidence Dossier

### 12.1 Get Aggregated Case Findings
- **Endpoint:** `GET /api/v1/cases/{case_id}/findings/aggregated`
- **Status:** `200 OK`
- **Response:** Array of `AggregatedFinding` objects combining forensic anomalies, consistency findings, relationship anomalies, and candidate conflicts with review history and epistemic classifications.

### 12.2 Record Investigator Review on Aggregated Finding
- **Endpoint:** `POST /api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews`
- **Status:** `201 Created`
- **Request Body:**
  ```json
  {
    "reviewer_id": "examiner-01",
    "action": "CONFIRM_OBSERVATION",
    "rationale": "Verified trailer xref tampering manually."
  }
  ```
- **Response:** Created `AggregatedFindingReview` object.

### 12.3 List Review History for an Aggregated Finding
- **Endpoint:** `GET /api/v1/cases/{case_id}/findings/aggregated/{finding_id}/reviews`
- **Status:** `200 OK`
- **Response:** Array of `AggregatedFindingReview` objects in chronological order.

### 12.4 Generate Investigation Evidence Dossier Draft
- **Endpoint:** `POST /api/v1/cases/{case_id}/dossiers/generate`
- **Status:** `201 Created`
- **Request Body:**
  ```json
  {
    "created_by": "lead-investigator",
    "scope_and_purpose": "Forensic audit and cross-document reconciliation"
  }
  ```
- **Response:** `InvestigationDossier` object with all 12 analytical sections, document summaries, and preliminary content hash.

### 12.5 List Case Dossiers
- **Endpoint:** `GET /api/v1/cases/{case_id}/dossiers`
- **Status:** `200 OK`
- **Response:** Array of `InvestigationDossier` objects.

### 12.6 Get Dossier Details
- **Endpoint:** `GET /api/v1/cases/{case_id}/dossiers/{dossier_id}`
- **Status:** `200 OK`
- **Response:** Full `InvestigationDossier` object including all 12 chapters, review decisions, and metadata.

### 12.7 Finalize Investigation Dossier
- **Endpoint:** `POST /api/v1/cases/{case_id}/dossiers/{dossier_id}/finalize`
- **Status:** `200 OK`
- **Request Body:**
  ```json
  {
    "user_id": "supervisor-01"
  }
  ```
- **Response:** Finalized `InvestigationDossier` with status `APPROVED` and canonical SHA-256 `content_hash`.

### 12.8 Export Dossier Artifact (PDF or JSON)
- **Endpoint:** `GET /api/v1/cases/{case_id}/dossiers/{dossier_id}/export`
- **Query Parameters:**
  - `format`: `pdf` or `json` (default: `pdf`).
  - `user_id`: Investigator identity requesting export.
- **Status:** `200 OK`
- **Response:** File attachment stream with `application/pdf` or `application/json` content-type, EVIDEXA branding, and legal disclaimers.

---

## 13. Grounded AI Investigation Assistant

### 13.1 Query Grounded Investigation Assistant
- **Endpoint:** `POST /api/v1/cases/{case_id}/assistant/query`
- **Description:** Submits an investigator question and receives a bounded, evidence-grounded response with traceable citations.
- **Request Body (`AssistantQueryRequest`):**
  ```json
  {
    "question": "Provide a case summary of all uploaded documents.",
    "conversation_context": [
      {"role": "user", "content": "What documents exist?"},
      {"role": "assistant", "content": "Document invoice_101.pdf has been uploaded."}
    ],
    "category_hint": "INVESTIGATION_SUMMARY",
    "reviewer_id": "senior-examiner"
  }
  ```
- **Question Categories:**
  - `EVIDENCE_EXPLANATION`
  - `CROSS_DOCUMENT_COMPARISON`
  - `ENTITY_INVESTIGATION`
  - `CONTRADICTION_ANALYSIS`
  - `INVESTIGATION_SUMMARY`
  - `FOLLOW_UP_SUGGESTIONS`
- **Status:** `200 OK`
- **Response (`AssistantQueryResponse`):**
  ```json
  {
    "case_id": "case-uuid",
    "question_category": "INVESTIGATION_SUMMARY",
    "answer_text": "Based on authoritative case records, 2 documents have been analyzed.",
    "citations": [
      {
        "citation_id": "[E-1]",
        "case_id": "case-uuid",
        "document_id": "doc-uuid",
        "document_title": "invoice_101.pdf",
        "evidence_id": null,
        "finding_id": null,
        "entity_id": null,
        "relationship_id": null,
        "page_number": 1,
        "bounding_box": null,
        "source_subsystem": "inventory",
        "relevant_text": "Primary invoice submitted for verification.",
        "target_route": "/cases/case-uuid/documents/doc-uuid/examine"
      }
    ],
    "observed_facts": [
      "Document invoice_101.pdf registered with SHA-256 e3b0c44..."
    ],
    "automated_indicators": [
      "PDF incremental update detected on trailer dictionary."
    ],
    "analytical_interpretations": [
      "Supplier name matches candidate entity."
    ],
    "contradictory_evidence": [],
    "unresolved_questions": [
      "Original signed paper contract remains unverified."
    ],
    "limitations": [
      "OCR ground truth unavailable for redacted regions."
    ],
    "follow_up_suggestions": [
      "Inspect trailer dictionary update timestamp in document examine workspace."
    ],
    "has_sufficient_evidence": true,
    "ai_notice": "AI-generated response grounded strictly in EVIDEXA case records.",
    "retrieval_stats": {
      "documents": 2,
      "findings": 1,
      "entities": 2,
      "total_items": 5
    },
    "model_name": "evidexa-mock-llm-v1"
  }
  ```

### 13.2 Retrieve Assistant Context Summary
- **Endpoint:** `GET /api/v1/cases/{case_id}/assistant/context-summary`
- **Description:** Retrieves counts and available evidentiary sources for active case initialization.
- **Status:** `200 OK`
- **Response:**
  ```json
  {
    "case_id": "case-uuid",
    "case_title": "Operation Apex Forensics",
    "case_status": "ACTIVE",
    "counts": {
      "documents": 2,
      "forensic_findings": 3,
      "consistency_findings": 1,
      "entities": 4,
      "relationships": 2,
      "reviews": 1,
      "total_items": 13
    },
    "document_titles": ["invoice_101.pdf", "receipt_202.pdf"],
    "unavailable_subsystems": []
  }
  ```





