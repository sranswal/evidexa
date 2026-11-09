# Domain Model Specification
**Project:** Enterprise Document Forensics & Contextual Intelligence Platform  
**Phase:** 2A — Foundation & Core Architecture  
**Document Type:** Domain Model, Entities, Enums, and Business Invariants  
**Date:** November 2026

---

## 1. Domain Entities & Value Objects

### 1.1 Spatial Geometry: PageGeometry & BoundingBox (Value Objects)
Defines the spatial bounding box geometry and canvas geometry for localized forensic evidence.
- **`PageGeometry` Specification:**
  - `width: float`: Physical/raster page width ($> 0$).
  - `height: float`: Physical/raster page height ($> 0$).
  - `rotation: int`: Clockwise page rotation angle in degrees ($\in \{0, 90, 180, 270\}$).
  - `dpi: Optional[float]`: Canvas raster resolution (default 72.0 for standard PDF points).
  - Properties: `is_portrait`, `is_landscape`, `aspect_ratio`, `rotated_dimensions()`.
- **`BoundingBox` Canonical Contract:**
  - Standard Origin: **Top-Left (0.0, 0.0)**.
  - Horizontal Axis ($X$): Increases from left to right $[0.0, 1.0]$.
  - Vertical Axis ($Y$): Increases from top to bottom $[0.0, 1.0]$.
  - **Zero Silent Clamping:** Any coordinate exceeding $[0.0, 1.0]$ or negative dimensions raises an immediate descriptive `ValueError`. Silent coordinate clamping is strictly prohibited.
  - Methods:
    - `from_pdf_points(x0, y0, x1, y1, page_width, page_height)`: Inverts native PDF bottom-left origin ($Y$ increasing upwards) to canonical top-left normalized coordinates.
    - `to_pdf_points(page_width, page_height)`: Inverts canonical top-left back to native PDF bottom-left points $(x_0, y_0, x_1, y_1)$.
    - `apply_rotation(page, rotation_degrees)`: Recomputes normalized coordinates across 90°, 180°, and 270° clockwise transforms.
    - `is_zero_area()`: Identifies point or line annotations (width = 0 or height = 0).

---

### 1.2 Case (Aggregate Root)
Represents a self-contained investigation workspace.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_reference: str`: Human-readable reference (e.g. `CASE-20261107-A4B1`).
  - `title: str`: Case title (1–255 characters).
  - `description: Optional[str]`: Contextual investigation overview.
  - `status: CaseStatus`: Current lifecycle state (`DRAFT`, `ACTIVE`, `UNDER_REVIEW`, `COMPLETED`, `ARCHIVED`).
  - `created_at: datetime`: Timezone-aware UTC timestamp.
  - `updated_at: datetime`: Timezone-aware UTC timestamp.
  - `created_by: Optional[str]`: Investigator identifier.
  - `metadata: Dict[str, Any]`: Structured contextual attributes.
- **Lifecycle Invariants:**
  - Status transitions are strictly validated:
    - `DRAFT` $\rightarrow$ `ACTIVE`, `ARCHIVED`
    - `ACTIVE` $\rightarrow$ `UNDER_REVIEW`, `ARCHIVED`
    - `UNDER_REVIEW` $\rightarrow$ `ACTIVE`, `COMPLETED`, `ARCHIVED`
    - `COMPLETED` $\rightarrow$ `UNDER_REVIEW`, `ARCHIVED`
    - `ARCHIVED` $\rightarrow$ `ACTIVE`
  - Unpermitted transitions raise `InvalidStatusTransitionException`.

---

### 1.3 Document (Entity)
Represents an immutable original evidence document.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Foreign key to parent Case.
  - `original_filename: str`: Sanitized uploaded filename.
  - `media_type: str`: Validated MIME media type (`application/pdf`, `image/png`, `image/jpeg`, `image/tiff`).
  - `file_extension: str`: Normalized extension (e.g. `.pdf`, `.png`).
  - `file_size_bytes: int`: Size in bytes ($> 0$).
  - `sha256: str`: Hex-encoded 64-character cryptographic digest calculated on raw uploaded bytes.
  - `storage_key: str`: Relative path within secure originals directory (`{case_id}/{document_id}.ext`).
  - `page_count: Optional[int]`: Total pages (nullable until parsed).
  - `document_type: Optional[DocumentType]`: Classification (`PAYSTUB`, `BANK_STATEMENT`, `ID_CARD`, `PASSPORT`, `INVOICE`, `CONTRACT`, `TAX_RETURN`, `UNKNOWN`).
  - `ingestion_status: IngestionStatus`: State (`PENDING`, `STORED`, `PROCESSING`, `PROCESSED`, `FAILED`).
  - `created_at: datetime`: Timezone-aware UTC timestamp.
  - `created_by: Optional[str]`: Uploader identifier.
  - `metadata: Dict[str, Any]`: File metadata (e.g., `duplicate_of_document_id`).
- **Invariants:**
  - Original uploaded files are strictly read-only and immutable. Analysis never modifies or overwrites the original file bytes.
  - SHA-256 hash must be verified during initial stream reading.
  - Duplicate documents are linked via metadata, never silently deleted or discarded.

---

### 1.4 ProcessingRun (Entity)
Tracks the execution of a forensic pipeline or analysis tool over one or more documents.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Foreign key to Case.
  - `document_ids: List[str]`: Target documents analyzed in this run.
  - `pipeline_name: str`: Tool or pipeline identifier (e.g. `pdf_structural_forensics`, `visual_ela_detector`).
  - `pipeline_version: str`: Semantic version string.
  - `status: PipelineStatus`: State (`QUEUED`, `RUNNING`, `SUCCEEDED`, `PARTIALLY_SUCCEEDED`, `FAILED`, `CANCELLED`).
  - `started_at: datetime`: UTC start timestamp.
  - `completed_at: Optional[datetime]`: UTC completion timestamp.
  - `error_code: Optional[str]`: Sanitized error code if failed.
  - `error_message: Optional[str]`: Sanitized error narrative.
  - `configuration_snapshot: Dict[str, Any]`: Pinned parameters used for this run.
  - `resource_metrics: Optional[Dict[str, Any]]`: CPU time, peak memory usage.
- **Invariants:**
  - Rerunning a pipeline creates a new `ProcessingRun` entity. Earlier run results are preserved.

---

### 1.5 EvidenceNode (Entity)
Represents an atomic, granular evidentiary observation (e.g. an OCR token, a high-frequency FFT spike, a modified PDF xref stream).
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Foreign key to Case.
  - `document_id: Optional[str]`: Target document (None for cross-document observations).
  - `processing_run_id: str`: Foreign key to originating ProcessingRun.
  - `evidence_type: EvidenceType`: `OCR_TEXT`, `EXTRACTED_FIELD`, `TABLE_CELL`, `VISUAL_REGION`, `PDF_STRUCTURAL`, `METADATA`, `CROSS_DOCUMENT`, `RULE_VALIDATION`, `REVIEW_ANNOTATION`.
  - `title: str`: Short description.
  - `description: str`: Detailed technical explanation.
  - `source_component: str`: Originating module name.
  - `source_version: str`: Module version.
  - `observed_at: datetime`: UTC timestamp.
  - `page_number: Optional[int]`: 1-based page number.
  - `bounding_box: Optional[BoundingBox]`: Physical or normalized coordinate bounding box.
  - `coordinate_system: Optional[CoordinateSystem]`: `NORMALIZED_0_1`, `PIXEL_EXACT`, `PDF_POINTS`.
  - `pdf_object_reference: Optional[str]`: Indirect PDF object ID (e.g. `12 0 R`).
  - `byte_offset_start: Optional[int]`: Byte offset in file stream.
  - `byte_offset_end: Optional[int]`: Ending byte offset.
  - `raw_value: Optional[str]`: Unprocessed textual value (masked in `repr` to protect PII).
  - `normalized_value: Optional[str]`: Formatted/canonicalized text.
  - `confidence: Optional[float]`: Statistical confidence constrained strictly to $[0.0, 1.0]$ or `None`.
  - `metadata: Dict[str, Any]`: Diagnostic parameters.

---

### 1.6 ForensicFinding (Entity)
An evidentiary interpretation or detected irregularity supported by underlying evidence records.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Foreign key to Case.
  - `document_id: Optional[str]`: Associated document.
  - `processing_run_id: str`: Originating run.
  - `category: FindingCategory`: `PDF_STRUCTURE`, `VISUAL_ANOMALY`, `DOCUMENT_INCONSISTENCY`, `FINANCIAL_VALIDATION`, `IDENTITY_VALIDATION`, `CROSS_DOCUMENT_MISMATCH`, `DUPLICATE_CONTENT`, `OTHER`.
  - `title: str`: Title of finding.
  - `description: str`: Forensic narrative.
  - `severity: FindingSeverity`: `INFO`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
  - `confidence: Optional[float]`: Confidence score $[0.0, 1.0]$.
  - `status: FindingStatus`: `DETECTED`, `NEEDS_REVIEW`, `CONFIRMED_OBSERVATION`, `DISMISSED`, `RESOLVED`.
  - `evidence_ids: List[str]`: Array of supporting `EvidenceNode` IDs.
  - `created_at: datetime`: UTC timestamp.
  - `source_component: str`: Generating component.
  - `limitations: List[str]`: Known caveats, false-positive risks, or boundaries.
  - `metadata: Dict[str, Any]`: Diagnostic details.
- **Invariants:**
  - Findings in all categories (except `OTHER`) **must reference at least one supporting EvidenceNode ID**. Unsupported assertions are rejected at validation time.
  - **No `is_fraud` Boolean:** A finding reflects an observed anomaly, never an automated declaration of criminal fraud.

---

### 1.7 InvestigationDossier (Aggregate)
Formal structured dossier summarizing findings, documents, and evidence.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Foreign key to Case.
  - `version: int`: Monotonically increasing version number ($\ge 1$).
  - `status: DossierStatus`: `DRAFT`, `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `SUPERSEDED`.
  - `executive_summary: str`: High-level narrative.
  - `document_summaries: List[Dict[str, Any]]`: Per-document summaries.
  - `finding_ids: List[str]`: Included findings.
  - `evidence_ids: List[str]`: Included evidence references.
  - `review_decisions: List[str]`: Human review decisions.
  - `limitations: List[str]`: Assessment caveats.
  - `created_at: datetime`: UTC timestamp.
  - `created_by: str`: Author identifier.
  - `finalized_at: Optional[datetime]`: Approval timestamp.
- **Invariants:**
  - Once a dossier is marked `APPROVED`, it becomes permanently immutable.
  - Edits require calling `create_next_version()`, which increments `version` and transitions the previous dossier to `SUPERSEDED`.

---

### 1.8 AuditEvent (Entity)
Cryptographically chained ledger entry recording all case activities.
- **Fields:**
  - `id: str`: Unique UUID4 identifier.
  - `case_id: str`: Associated Case.
  - `sequence_number: int`: Monotonically increasing sequence number ($\ge 1$).
  - `actor_id: Optional[str]`: User or service performing action.
  - `event_type: AuditEventType`: Type of event.
  - `entity_type: EntityType`: Entity acted upon.
  - `entity_id: str`: Primary key of entity.
  - `timestamp: datetime`: UTC timestamp.
  - `payload: Dict[str, Any]`: Event payload.
  - `previous_event_hash: Optional[str]`: SHA-256 digest of preceding event in case ledger.
  - `event_hash: str`: SHA-256 digest over canonicalized event string.
  - `schema_version: str`: Ledger schema format version (default `"1.0"`).
- **Invariants:**
  - Hash is computed over canonical JSON payload, sequence number, and normalized UTC timestamps.
  - Tampering, modifying payload, reordering, or deleting entries breaks the hash chain and sequence continuity.

---

### 1.9 AuditCheckpoint (Entity)
Independently synchronized trusted head of an audit chain per case.
- **Fields:**
  - `case_id: str`: Primary key to Case.
  - `head_event_id: str`: ID of latest recorded event.
  - `head_event_hash: str`: SHA-256 digest of latest event.
  - `event_count: int`: Total number of events sealed in the ledger.
  - `updated_at: datetime`: UTC timestamp of latest checkpoint sync.
- **Invariants:**
  - Checkpoint updates are executed in the same database transaction as audit event persistence.
  - Protects against tail truncation attacks (deleting the most recent event from the hash chain).

---

### 1.10 OCR & Document Understanding Models (Domain Models)
Pure domain models representing text tokens, reading order, lines, blocks, layout regions, and tabular structures extracted from documents.
- **`TextToken`**:
  - `id: str`: Deterministic or UUID4 token ID.
  - `raw_text: str`: Exact raw character sequence extracted by engine (unmodified).
  - `normalized_text: Optional[str]`: Cleaned, normalized text for search indexing.
  - `bounding_box: Optional[BoundingBox]`: Normalized $[0.0, 1.0]$ canonical top-left coordinates.
  - `confidence: Optional[float]`: Honest calibrated confidence $[0.0, 1.0]$ (`None` if uncalibrated).
  - `is_uncertain: bool`: Flag indicating uncertain coordinates or low engine certainty.
- **`TextLine`**:
  - `id: str`: Line identifier.
  - `raw_text: str`: Full line string.
  - `normalized_text: Optional[str]`: Normalized search line string.
  - `bounding_box: Optional[BoundingBox]`: Minimum bounding box enclosing line tokens.
  - `confidence: Optional[float]`: Honest line-level confidence.
  - `tokens: List[TextToken]`: Ordered constituent tokens.
  - `reading_order_index: int`: Deterministic reading order sequence within page ($\ge 0$).
- **`TextBlock`**:
  - `id: str`: Text block identifier.
  - `block_type: LayoutRegionType`: Semantic block type (`HEADER`, `FOOTER`, `PARAGRAPH`, etc.).
  - `raw_text: str`: Block concatenated raw text.
  - `normalized_text: Optional[str]`: Block normalized text.
  - `bounding_box: Optional[BoundingBox]`: Enclosing bounding box.
  - `lines: List[TextLine]`: Ordered constituent text lines.
  - `reading_order_index: int`: Reading order position on page.
- **`ExtractedTableCell` & `ExtractedTable`**:
  - `ExtractedTableCell`: `row_index: int`, `col_index: int`, `row_span: int = 1`, `col_span: int = 1`, `raw_text: str`, `normalized_text: Optional[str]`, `bounding_box: Optional[BoundingBox]`, `confidence: Optional[float]`, `is_header: bool`.
  - `ExtractedTable`: `num_rows: int`, `num_cols: int`, `cells: List[ExtractedTableCell]`, `bounding_box: Optional[BoundingBox]`, `caption: Optional[str]`.
- **`LayoutRegion`**:
  - `id: str`: Layout region ID.
  - `region_type: LayoutRegionType`: Semantic category (`HEADER`, `FOOTER`, `TITLE`, `PARAGRAPH`, `TABLE`, `FIGURE`, `CAPTION`, `LIST`, `KEY_VALUE`, `UNKNOWN`).
  - `bounding_box: Optional[BoundingBox]`: Normalized page region extent.
  - `confidence: Optional[float]`: Region classification confidence.
  - `reading_order_index: int`: Sequence index in reading order.
  - `associated_block_ids: List[str]`: References to constituent text blocks.
- **`ExtractedPage` & `ExtractedDocumentText`**:
  - `ExtractedPage`: `page_number: int` (1-indexed), `geometry: PageGeometry`, `raw_text: str`, `normalized_text: Optional[str]`, `tokens: List[TextToken]`, `lines: List[TextLine]`, `blocks: List[TextBlock]`, `tables: List[ExtractedTable]`, `layout_regions: List[LayoutRegion]`, `has_vector_text: bool`, `extraction_status: str`, `engine_name: Optional[str]`, `routing_decision: Optional[str]`, `routing_reason: Optional[str]`, `alternative_extractions: Dict[str, Any]`.
  - `ExtractedDocumentText`: `document_id: str`, `total_pages: int`, `pages: List[ExtractedPage]`, `engine_metadata: OcrEngineMetadata`.
- **Evidentiary Invariants:**
  - Raw text is strictly preserved without mutation or lossy stripping; normalization is stored separately in `normalized_text`.
  - Token coordinates reside in canonical `NORMALIZED_0_1` top-left coordinates matching visual forensics and PDF structural coordinates.
  - Optical OCR and vector extractions preserve engine provenance per page.
  - Uncalibrated confidence scores are strictly preserved as nullable (`None` for programmatic vector extraction where confidence is uncalibrated with `metadata['confidence_calibration_method'] = 'not_applicable_vector_extraction'`, and raw float probabilities for optical recognition with `metadata['confidence_calibration_method'] = 'uncalibrated_model_score'`).
  - Partial extractions with failed pages are explicitly marked with `extraction_status = 'FAILED'`, `error_message`, and `PipelineStatus.PARTIALLY_SUCCEEDED` on the processing run.
  - The complete granular extraction tree is persisted via `DocumentStorageProtocol.store_artifact()`, while structural highlights are indexed as `EvidenceNode` instances in relational storage.

---

### 1.11 Document Classification & Structured Field Extraction (Phase 2C.2)

#### 1.11.1 Document Classification Models
- **`DocumentClass` (Enum):**
  - `INVOICE`, `RECEIPT`, `BANK_STATEMENT`, `IDENTITY_DOCUMENT`, `TAX_DOCUMENT`, `CONTRACT`, `UNKNOWN`.
- **`ClassificationCandidate` (Value Object):**
  - `document_class: DocumentClass`: Evaluated candidate class.
  - `ranking_score: float`: Rule ranking score $[0.0, 1.0]$.
  - `matched_signals: List[str]`: Lexical/regex pattern signals matched in document text.
- **`PageClassification` (Value Object):**
  - `page_number: int`: Page index ($\ge 1$).
  - `predicted_class: DocumentClass`: Top predicted class for this page.
  - `ranking_score: float`: Ranking score for the page.
  - `candidates: List[ClassificationCandidate]`: Ranked candidates for this page.
  - `matched_signals: List[str]`: Page-level matched patterns.
- **`ClassificationOverride` (Value Object):**
  - `original_class: DocumentClass`: Preserved machine-predicted class.
  - `overridden_class: DocumentClass`: Investigator-assigned class.
  - `overridden_by: str`: Investigator user/service ID.
  - `reason: str`: Mandatory justification for review override.
  - `overridden_at: datetime`: UTC timestamp of override event.
- **`DocumentClassificationResult` (Aggregate):**
  - `document_id: str`: Analyzed document identifier.
  - `processing_run_id: str`: Execution run ID.
  - `predicted_class: DocumentClass`: Top machine-predicted class.
  - `effective_class: DocumentClass`: Current effective class (`overridden_class` if overridden, else `predicted_class`).
  - `ranking_score: float`: Ranking score ($[0.0, 1.0]$).
  - `score_type: str`: `"rule_ranking_score"`.
  - `classification_method: str`: Algorithm identifier (`rule_pattern_classifier_v1`).
  - `candidates: List[ClassificationCandidate]`: Candidate class rankings sorted descending by score.
  - `page_classifications: List[PageClassification]`: Individual page classifications.
  - `manual_override: Optional[ClassificationOverride]`: Present if overridden.

#### 1.11.2 Structured Extraction Models & Provenance
- **`FieldDataType` (Enum):**
  - `STRING`, `NUMBER`, `DECIMAL`, `DATE`, `CURRENCY`, `MASKED_STRING`, `BOOLEAN`, `ARRAY`.
- **`FieldValidationStatus` (Enum):**
  - `VALID`, `WARNING`, `INVALID`, `UNVALIDATED`.
- **`FieldDefinition` (Value Object):**
  - `field_key: str`: Unique machine key.
  - `label: str`: Human-readable field label.
  - `data_type: FieldDataType`: Target data type.
  - `required: bool`: Whether field is mandatory in schema.
  - `aliases: List[str]`: Lexical aliases/labels used for extraction.
  - `description: Optional[str]`: Contextual definition.
- **`ExtractionSchema` (Aggregate):**
  - `schema_id: str` (e.g. `invoice_v1`, `receipt_v1`, `bank_statement_v1`).
  - `name: str`: Descriptive schema name.
  - `target_class: DocumentClass`: Associated document class.
  - `version: str`: Schema semver version string.
  - `fields: List[FieldDefinition]`: List of defined schema fields.
- **`CandidateValue` (Value Object):**
  - `raw_text: str`: Raw matched string.
  - `normalized_value: Any`: Cleaned/converted value.
  - `score: float`: Candidate match ranking score.
  - `page_number: int`: Source page number.
  - `bounding_box: Optional[BoundingBox]`: Enclosing spatial bounding box.
  - `token_ids: List[str]`: IDs of supporting OCR tokens.
- **`ExtractedFieldValue` (Entity):**
  - `field_key: str`, `label: str`, `normalized_value: Any`, `raw_text: str`, `data_type: FieldDataType`, `extraction_method: str`, `score: float`.
  - `confidence: None`: Explicitly `None` for deterministic rule extractions.
  - `confidence_explanation: str`: Transparent evidentiary disclaimer.
  - `source_document_id: str`, `source_page_number: int`.
  - `source_bounding_boxes: List[BoundingBox]`: Source spatial coordinates.
  - `source_token_ids: List[str]`: Lineage to atomic OCR tokens.
  - `validation_status: FieldValidationStatus`, `warnings: List[str]`.
  - `alternative_candidates: List[CandidateValue]`: Ranked lower-scoring alternative extractions.
  - `evidence_node_id: Optional[str]`: Linkage to persisted Evidence Graph node (`EXTRACTED_FIELD`).
- **`DocumentExtractionResult` (Aggregate):**
  - `document_id: str`, `processing_run_id: str`, `schema_id: str`, `schema_version: str`, `fields: Dict[str, ExtractedFieldValue]`, `validation_summary: Dict[str, Any]`, `execution_duration_ms: float`, `storage_artifact_key: Optional[str]`.
- **Evidentiary & Security Invariants (Phase 2C.2.1 Hardened):**
  - **Financial Precision (Python `Decimal`):** Monetary amounts are represented strictly as `Decimal` instances. Conversions to/from IEEE 754 binary `float` are prohibited. Quantization and arithmetic checks obey explicit currency minor units (e.g., 0 for JPY, 3 for KWD, 2 for USD/EUR) with a default 0.05 tolerance. Discrepancies generate `WARNING` statuses, not fraud conclusions.
  - **Zero Plaintext PII Persistence:** Sensitive account numbers are masked (`****{last4}` for $\ge 4$ characters, `****` for $< 4$) at regex match time. Plaintext unmasked values never appear in `CandidateValue.raw_text`, `ExtractedFieldValue.raw_text`, `EvidenceNode.raw_value`, extraction artifacts, database records, or logs.
  - **Date & Currency Ambiguity Preservation:** Numeric dates with ambiguous day/month values ($\le 12$) and ambiguous currency symbols (`$`, `¥`) evaluate to `None` with candidate interpretations and validation warnings unless resolved by explicit document context. Unknown currencies are never fabricated.
  - **Asserted Reviewer Identity & Local Tamper-Evident Ledger:** `overridden_by` represents an asserted reviewer identifier in unauthenticated development mode. Overrides record to the local hash-chained append-only audit ledger.
  - **No Fake Bounding Boxes:** If supporting OCR tokens lack bounding boxes, `source_bounding_boxes` remains `[]`; synthetic or fabricated boxes are never generated.
  - **Artifact SHA-256 Verification & Rerun Isolation:** Persisted extraction JSON artifacts are verified via SHA-256 upon reload. Repeated extractions create distinct `ProcessingRun` records and independent files without overwriting previous evidence.
  - **Explainable Ranking:** Field scores reflect rule specificity weights, not probabilistic model confidences.
  - **Full Evidence Graph Linkage:** Every extracted field creates an `EvidenceNode` in SQLite with `evidence_type = EXTRACTED_FIELD` for cross-document queryability.

### 1.12 Cross-Document Entity Resolution (Phase 2C.3.1)

#### 1.12.1 Entity Resolution Domain Models
- **`ResolvedEntityType` (Enum):**
  - `ORGANIZATION`, `PERSON`, `TAX_IDENTIFIER`, `INVOICE_REFERENCE`, `BANK_ACCOUNT_REFERENCE`, `CURRENCY_AMOUNT`, `TRANSACTION_REFERENCE`.
- **`EntityMatchClassification` (Enum):**
  - `EXACT_MATCH`, `NORMALIZED_EXACT_MATCH`, `STRONG_CANDIDATE`, `WEAK_AMBIGUOUS`, `CONFLICTING_IDENTITY`, `INSUFFICIENT_EVIDENCE`.
- **`MatchDecisionStatus` (Enum):**
  - `ALGORITHMIC_CANDIDATE`, `CONFIRMED`, `REJECTED`, `AMBIGUOUS`.
- **`HumanReviewStatus` (Enum):**
  - `UNREVIEWED`, `CONFIRMED`, `REJECTED`, `AMBIGUOUS`.
- **`EntityMatchingMethod` (Enum):**
  - `EXACT_IDENTIFIER`, `EXACT_REFERENCE`, `NORMALIZED_EXACT`, `ORGANIZATION_NAME_SIMILARITY`, `PERSON_NAME_SIMILARITY`, `COMPOSITE_SIGNALS`, `CONTRADICTION_DETECTED`, `RULE_FALLBACK`.
- **`EntityMention` (Value Object):**
  - `mention_id: str`, `case_id: str`, `document_id: str`, `page_number: int`, `processing_run_id: str`, `field_key: str`, `entity_type: ResolvedEntityType`.
  - `original_value: str`: Sanitized original text (masked account numbers, never unmasked plaintext).
  - `normalized_value: str`: Canonical comparison string.
  - `numeric_amount: Optional[Decimal]`, `currency_code: Optional[str]`, `jurisdiction: Optional[str]`, `identifier_type: Optional[str]`, `legal_suffix: Optional[str]`, `base_name: Optional[str]`.
  - `supporting_evidence_node_ids: List[str]`, `bounding_boxes: List[BoundingBox]`.
- **`EntityMatchEvidence` (Value Object):**
  - `target_mention_id: str`, `candidate_mention_id: str`, `target_document_id: str`, `candidate_document_id: str`, `target_evidence_node_ids: List[str]`, `candidate_evidence_node_ids: List[str]`, `matching_signals: List[str]`, `contradicting_signals: List[str]`, `resolution_algorithm_version: str`.
- **`EntityCandidateMatch` (Entity):**
  - `id: str`, `case_id: str`, `processing_run_id: str`, `entity_type: ResolvedEntityType`, `target_mention_id: str`, `candidate_mention_id: str`, `matching_method: EntityMatchingMethod`, `match_classification: EntityMatchClassification`, `match_score: float` $[0.0, 1.0]$, `score_semantics: str`, `decision_status: MatchDecisionStatus`, `review_status: HumanReviewStatus`, `evidence: EntityMatchEvidence`, `review_history: List[HumanMatchReview]`.
- **`HumanMatchReview` (Entity):**
  - `id: str`, `match_id: str`, `case_id: str`, `decision: EntityReviewAction` (`CONFIRM_MATCH`, `REJECT_MATCH`, `MARK_AMBIGUOUS`), `reviewer_id: str`, `reason: str`, `reviewed_at: datetime`, `previous_status: MatchDecisionStatus`, `new_status: MatchDecisionStatus`.
- **`ResolvedEntity` (Aggregate):**
  - `id: str`, `case_id: str`, `entity_type: ResolvedEntityType`, `canonical_name: str`, `mention_ids: List[str]`, `document_ids: List[str]`, `confidence_score: float`, `is_confirmed: bool`, `candidate_match_ids: List[str]`.
- **`EntityResolutionResult` (Aggregate):**
  - `case_id: str`, `processing_run_id: str`, `total_mentions: int`, `total_comparisons: int`, `candidate_matches: List[EntityCandidateMatch]`, `resolved_entities: List[ResolvedEntity]`, `unresolved_mentions: List[EntityMention]`, `blocking_summary: Dict[str, int]`, `execution_duration_ms: float`, `storage_artifact_key: Optional[str]`, `storage_artifact_sha256: Optional[str]`.

#### 1.12.2 Evidentiary Invariants
- **Similarity is not Identity:** A strong similarity score or matching name never automatically converts into a confirmed real-world identity. Candidate matches retain uncertainty and require corroborating identifiers or human review confirmation.
- **Strict Case Isolation:** Mention comparisons and entity clustering are strictly bounded within a single case. Cross-case matching is blocked at engine entry with `SecurityException`.
- **Contradiction Precedence:** Contradicting identifiers (e.g. conflicting tax IDs on organizations with similar names, or differing currencies on identical monetary amounts) immediately override similarity and classify as `CONFLICTING_IDENTITY`, suppressing cluster formation.
- **Weak Masked Account Evidence:** Matching masked last-4 bank account digits are capped at `WEAK_AMBIGUOUS` with scores $\le 0.40$ due to collision probability.
- **Zero Plaintext PII:** Sensitive account numbers are masked immediately; plaintext digits never appear in mentions, matches, evidence nodes, database rows, or artifacts.

### 1.13 Cross-Document Relationship Detection & Ontology (Phases 2C.3.2 & 2C.3.2.1)

#### 1.13.1 Relationship Detection Enums
- **`RelationshipType` (Enum - Ontology Version 2.0):**
  - Directed Document-Entity: `ISSUED` (Supplier/Merchant/Bank --ISSUED--> Document), `BILLED_TO` (Invoice --BILLED_TO--> Buyer), `HELD_BY` (Account --HELD_BY--> Account Holder).
  - Commercial Invoicing: `INVOICED` (Supplier --INVOICED--> Buyer, single invoice billing event).
  - Document-Document: `REFERENCES_PURCHASE_ORDER`, `REFERENCES_INVOICE`, `REFERENCES_RECEIPT`, `SUPPORTS_DOCUMENT`, `DUPLICATE_OF`, `AMENDS_DOCUMENT`.
  - Financial Transaction: `RECORDS_PAYMENT`, `CONTAINS_TRANSACTION`, `MAY_SETTLE`, `REFUNDS`, `TRANSFERS_TO`.
  - Corporate / Entity Roles: `REPRESENTS` (Person --REPRESENTS--> Organization).
  - Explicit Contractual Relationships: `SUPPLIES` (**strictly reserved** for explicit contractual supply agreements), `CUSTOMER_OF`.
  - Legacy Aliases (preserved for backwards-compatible reading of historical records): `ISSUED_BY`, `ISSUED_TO`, `ACCOUNT_HELD_BY`.
- **`DuplicateKind` (Enum):**
  - `BYTE_IDENTICAL`: Content verified identical by SHA-256 digest equality.
  - `VISUALLY_SIMILAR`: Visual layout similarity with distinct content hashes.
  - `SEMANTICALLY_SIMILAR`: Similar titles, extracted fields, or OCR tokens with distinct byte hashes.
  - `UNRESOLVED_DUPLICATE_CANDIDATE`: Candidate match requiring investigator review.
- **`StatusDeterminationMethod` (Enum):**
  - `EVIDENTIARY_RULE`: Status assigned strictly by deterministic heuristic logic and source evidence.
  - `HUMAN_REVIEW`: Status assigned or updated by investigator review decision.
- **`RelationshipStatus` (Enum):**
  - `CONFIRMED`: Verified by unequivocal documentation, matching references, byte-identical content, or human review confirmation.
  - `CANDIDATE`: Algorithmic hypothesis supported by standard heuristics; requires corroboration.
  - `CONTRADICTED`: Suppressed or invalidated by conflicting evidence (e.g. tax ID or currency mismatch).
  - `UNRESOLVED`: Insufficient evidence to establish relationship (e.g. amount coincidence without reference).
  - `REJECTED`: Disproven or rejected during human review.
- **`RelationshipReviewAction` (Enum):**
  - `CONFIRM_RELATIONSHIP`, `REJECT_RELATIONSHIP`, `MARK_UNRESOLVED`.
- **`RelationshipDetectionMethod` (Enum):**
  - `EXPLICIT_FIELD_REFERENCE`: Direct schema reference (e.g. invoice `supplier_name`, `buyer_name`).
  - `EXPLICIT_DOCUMENT_REFERENCE`: Exact citation pattern found in raw document text (e.g. PO, amendment).
  - `DOCUMENT_HASH_EQUALITY`: SHA-256 digest equality establishing byte identity.
  - `BYTE_EQUALITY_VERIFICATION`: Direct byte comparison between stored files.
  - `INVOICE_BILLING_EVENT_RULE`: Single commercial invoice linking supplier and buyer (`INVOICED`).
  - `CONTRACT_CLAUSE_RULE`: Explicit contract clause establishing ongoing supply (`SUPPLIES`).
  - `TRANSACTION_SETTLEMENT_RULE`: Heuristic matching between transactions and invoices.
  - `PAYMENT_REFERENCE_RULE`: Payment authorization codes or terminal slips.
  - `ROLE_REPRESENTATION_RULE`: Explicit corporate representation clauses.
  - `AMOUNT_COINCIDENCE_HEURISTIC`: Weak signal based solely on amount and/or date proximity.
  - `SEMANTIC_SIMILARITY_HEURISTIC`: Content/title similarity without byte equality.

#### 1.13.2 Relationship Domain Models
- **`RelationshipMention` (Value Object):**
  - `entity_id: str`, `document_id: str`, `mention_id: Optional[str]`, `role: str`, `raw_text: str`, `normalized_text: str`.
- **`RelationshipEvidence` (Value Object):**
  - `detection_method: RelationshipDetectionMethod`, `confidence_score: float` $[0.0, 1.0]$, `confidence_explanation: str`, `source_field_key: Optional[str]`, `target_field_key: Optional[str]`, `source_evidence_node_ids: List[str]`, `target_evidence_node_ids: List[str]`, `supporting_signals: List[str]`, `contradicting_signals: List[str]`, `detector_name: str`, `metadata: Dict[str, Any]`.
- **`RelationshipReviewRecord` (Entity):**
  - `id: str`, `relationship_id: str`, `case_id: str`, `decision: RelationshipReviewAction`, `reviewer_id: str`, `reason: str`, `reviewed_at: datetime`, `previous_status: RelationshipStatus`, `new_status: RelationshipStatus`.
- **`DetectedRelationship` (Entity):**
  - `id: str`, `case_id: str`, `processing_run_id: str`, `ontology_version: str`, `relationship_type: RelationshipType`, `legacy_relationship_type: Optional[str]`, `status: RelationshipStatus`, `status_determination_method: StatusDeterminationMethod`, `status_rationale: Optional[str]`, `duplicate_kind: Optional[DuplicateKind]`, `source_id: str`, `source_type: str`, `target_id: str`, `target_type: str`, `confidence_score: float`, `confidence_explanation: str`, `evidence: RelationshipEvidence`, `is_human_reviewed: bool`, `human_review_status: Optional[str]`, `review_history: List[RelationshipReviewRecord]`, `created_at: datetime`, `updated_at: datetime`.
- **`RelationshipCandidate` (Value Object):**
  - Draft relationship proposed by specialized detector before engine deduplication and contradiction checking.
- **`RelationshipDetectionRun` (Aggregate / Value Object):**
  - `id: str`, `case_id: str`, `detector_count: int`, `detected_relationships_count: int`, `confirmed_count: int`, `candidate_count: int`, `contradicted_count: int`, `unresolved_count: int`, `rejected_count: int`, `execution_time_ms: float`, `storage_path: Optional[str]`, `storage_sha256: Optional[str]`, `created_at: datetime`.
- **`RelationshipDetectionResult` (Aggregate):**
  - `case_id: str`, `run: RelationshipDetectionRun`, `relationships: List[DetectedRelationship]`.

#### 1.13.3 Evidentiary Invariants & Non-Goals
- **Directed Subject-Predicate-Object Graphs:** Relationships strictly follow directed Subject-Predicate-Object semantics (`source_id` $\rightarrow$ `target_id`). Examples: `Supplier --ISSUED--> Invoice`, `Invoice --BILLED_TO--> Buyer`, `Supplier --INVOICED--> Buyer` (single billing event), `Merchant --ISSUED--> Receipt`, `Bank --ISSUED--> Bank statement`, `Account --HELD_BY--> Holder`, `Person --REPRESENTS--> Org`, `Document --DUPLICATE_OF--> Document`.
- **Single Invoicing $\neq$ Ongoing Supply Arrangement:** Co-occurrence on an invoice establishes an invoicing event (`INVOICED`), never an ongoing business arrangement (`SUPPLIES`). `SUPPLIES` and `CUSTOMER_OF` are strictly reserved for explicit contract clauses.
- **Status vs. Score Separation:** Status (`CONFIRMED`, `CANDIDATE`, `CONTRADICTED`, `UNRESOLVED`, `REJECTED`) is governed strictly by deterministic evidentiary rules and human review decisions (`StatusDeterminationMethod`), never by raw scores. Scores represent heuristic ranking weights, not probabilities, and cannot independently promote candidates to confirmed.
- **Byte Identity vs. Cryptographic Hash Collisions:** Equal SHA-256 digests represent identical byte payloads (`DOCUMENT_HASH_EQUALITY`), never described as 'cryptographic hash collisions' (which occur when distinct files yield identical digests). `DuplicateKind` distinguishes `BYTE_IDENTICAL` from `VISUALLY_SIMILAR` and `SEMANTICALLY_SIMILAR`.
- **Contradiction Persistence Under Review:** When an investigator manually confirms a relationship despite contradictory signals, all contradictory signals remain completely visible in the evidence payload alongside reviewer justification.
- **Entity Match $\neq$ Relationship:** Entity resolution equates identities (e.g. Acme Corp on Document A is Acme Corp on Document B). It does not mean Document A caused Document B, or that a transaction occurred.
- **Candidate $\neq$ Proof:** A candidate relationship is an evidentiary hypothesis for human or agentic evaluation; it is not legal proof of an event.
- **Amount & Date Coincidence Limitation:** Amount equality and date proximity alone never establish payment settlement. Without explicit invoice citations or account linkages, coincidental matches remain `UNRESOLVED` with low confidence ($0.35$).
- **Contradiction Precedence:** Conflicting tax IDs or mismatched currencies immediately override similarity, marking relationships `CONTRADICTED` with confidence $0.0$.
- **Non-Fabrication of Bank Transactions:** The `bank_statement_v1` schema extracts only header and summary balances. In the absence of extracted transaction line items, transaction settlement nodes are never fabricated.
- **Masked Account Matches:** Masked bank account last-4 matches are weak evidence only (`score <= 0.40`).
- **Strict Case Isolation:** All relationship evaluations and lookups are strictly bounded within a single case. Cross-case queries return HTTP 404 (`SecurityException`).
- **Zero Plaintext PII Persistence:** Account numbers are masked immediately; plaintext account digits never enter relational tables, artifacts, or logs.


