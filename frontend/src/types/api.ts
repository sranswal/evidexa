/**
 * EVIDEXA API Data Types & Domain Enums
 * Grounded strictly in backend domain models.
 */

export type CaseStatus = "DRAFT" | "ACTIVE" | "UNDER_REVIEW" | "COMPLETED" | "ARCHIVED";

export type IngestionStatus =
  | "PENDING"
  | "STORED"
  | "PARSED"
  | "FAILED"
  | "PROCESSING"
  | "QUARANTINED";

export type DocumentType =
  | "UNKNOWN"
  | "PAYSTUB"
  | "BANK_STATEMENT"
  | "ID_CARD"
  | "PASSPORT"
  | "INVOICE"
  | "RECEIPT"
  | "PURCHASE_ORDER"
  | "IDENTITY_DOCUMENT"
  | "TAX_DOCUMENT"
  | "CONTRACT"
  | "TAX_RETURN";

export type DocumentClass =
  | "INVOICE"
  | "RECEIPT"
  | "PURCHASE_ORDER"
  | "BANK_STATEMENT"
  | "IDENTITY_DOCUMENT"
  | "TAX_DOCUMENT"
  | "CONTRACT"
  | "UNKNOWN";

export type FindingSeverity = "INFORMATIONAL" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type RelationshipEvidentiaryStatus = "CONFIRMED" | "CANDIDATE" | "CONTRADICTED" | "UNRESOLVED";

export type EpistemicClassification =
  | "OBSERVED_FACT"
  | "AUTOMATED_INDICATOR"
  | "ANALYTICAL_INTERPRETATION"
  | "INVESTIGATOR_CONCLUSION";

export type EvidentiaryClassification =
  | EpistemicClassification
  | RelationshipEvidentiaryStatus;

export type InvestigatorReviewAction =
  | "MARK_NEEDS_REVIEW"
  | "CONFIRM_OBSERVATION"
  | "DISMISS_FALSE_POSITIVE"
  | "MARK_INCONCLUSIVE"
  | "REQUEST_MORE_EVIDENCE";

export type AggregatedFindingCategory =
  | "DOCUMENT_INTEGRITY"
  | "VISUAL_ANOMALY"
  | "STRUCTURAL_ANOMALY"
  | "EXTRACTION_ANOMALY"
  | "CROSS_DOCUMENT_INCONSISTENCY"
  | "ENTITY_IDENTITY_CONFLICT"
  | "RELATIONSHIP_ANOMALY"
  | "DUPLICATE_OR_CONFLICTING_RECORD"
  | "OTHER";

export type DossierStatus = "DRAFT" | "PENDING_REVIEW" | "APPROVED" | "REJECTED" | "SUPERSEDED" | "IN_REVIEW" | "EXPORTED";

export interface Case {
  id: string;
  case_reference: string;
  title: string;
  description: string | null;
  status: CaseStatus;
  created_at: string;
  updated_at: string;
  created_by: string | null;
  metadata: Record<string, unknown>;
}

export interface CaseListResponse {
  items: Case[];
  total: number;
  skip: number;
  limit: number;
}

export interface DocumentItem {
  id: string;
  case_id: string;
  original_filename: string;
  media_type: string;
  file_extension: string;
  file_size_bytes: number;
  sha256: string;
  storage_key: string;
  page_count: number | null;
  document_type: DocumentType | null;
  ingestion_status: IngestionStatus;
  created_at: string;
  created_by: string | null;
  metadata: Record<string, unknown>;
}

export interface DocumentListResponse {
  items: DocumentItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface ForensicFinding {
  id: string;
  document_id: string | null;
  case_id?: string;
  processing_run_id: string;
  category?: string;
  finding_type?: string;
  severity: FindingSeverity;
  title: string;
  description: string;
  rule_id: string | null;
  page_number: number | null;
  confidence: number | null;
  status?: string;
  evidence_ids?: string[];
  limitations?: string[];
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface FindingListResponse {
  items: ForensicFinding[];
  total: number;
  skip: number;
  limit: number;
}

export interface AggregatedFindingReview {
  id: string;
  case_id: string;
  finding_id: string;
  action: InvestigatorReviewAction;
  reviewer_id: string;
  comment: string;
  reviewed_at: string;
  previous_status: string;
  new_status: string;
  rationale?: string;
  prior_status?: string;
  created_at?: string;
}

export interface FindingLocation {
  document_id?: string;
  page_number?: number;
  bounding_box?: [number, number, number, number];
  field_name?: string;
  evidence_id?: string;
  evidence_key?: string;
  [key: string]: unknown;
}

export interface AggregatedFinding {
  id: string;
  case_id: string;
  source_type?: string;
  source_id?: string;
  category?: AggregatedFindingCategory;
  evidentiary_classification?: EvidentiaryClassification;
  source_status?: string;
  review_status?: string;
  title: string;
  description: string;
  explanation?: string;
  severity: FindingSeverity;
  confidence?: number | null;
  affected_document_ids?: string[];
  affected_entity_ids?: string[];
  supporting_evidence_ids?: string[];
  contradicting_evidence_ids?: string[];
  locations?: FindingLocation[];
  limitations?: string[];
  is_reviewed?: boolean;
  review_history?: AggregatedFindingReview[];
  created_at: string;

  // Backward compatibility fields
  finding_source?: "FORENSIC" | "CONSISTENCY";
  source_finding_id?: string;
  document_id?: string | null;
  document_ids?: string[];
  rule_id?: string | null;
  confidence_score?: number;
  evidentiary_status?: EvidentiaryClassification;
  active_review_decision?: string | null;
  review_count?: number;
  updated_at?: string;
}

export interface ReviewCreateRequest {
  reviewer_id: string;
  action: InvestigatorReviewAction;
  rationale: string;
}

export interface DetectedRelationship {
  id: string;
  case_id: string;
  relationship_type: string;
  source_id: string;
  source_type: string;
  target_id: string;
  target_type: string;
  confidence_score: number;
  evidentiary_status: EvidentiaryClassification;
  created_at: string;
}

export interface PaginatedRelationshipsResponse {
  ontology_version: string;
  items: DetectedRelationship[];
  total: number;
  skip: number;
  limit: number;
}

export interface ProcessingRun {
  id: string;
  case_id?: string;
  pipeline_name: string;
  run_type?: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  document_ids?: string[];
  config?: Record<string, unknown>;
}

export interface ProcessingRunListResponse {
  items: ProcessingRun[];
  total: number;
  skip: number;
  limit: number;
}

export interface AnalyzerInfo {
  analyzer_id: string;
  display_name: string;
  version: string;
}

export interface EvidenceNode {
  id: string;
  case_id: string;
  document_id: string;
  processing_run_id?: string;
  evidence_type: string;
  source_component: string;
  page_number: number | null;
  bounding_box: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  raw_value?: string | null;
  normalized_value?: string | null;
  confidence: number | null;
  title: string;
  description: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface EvidenceListResponse {
  items: EvidenceNode[];
  total: number;
  skip: number;
  limit: number;
}

export interface ClassificationCandidate {
  document_class: DocumentClass;
  ranking_score: number;
  matched_signals: string[];
}

export interface PageClassification {
  page_number: number;
  predicted_class: DocumentClass;
  ranking_score: number;
  candidates: ClassificationCandidate[];
  matched_signals: string[];
}

export interface DocumentClassificationResult {
  document_id: string;
  processing_run_id: string;
  predicted_class: DocumentClass;
  effective_class: DocumentClass;
  ranking_score: number;
  score_type: string;
  classification_method: string;
  candidates: ClassificationCandidate[];
  page_classifications: PageClassification[];
  manual_override?: {
    original_class: DocumentClass;
    overridden_class: DocumentClass;
    overridden_by: string;
    reason: string;
    overridden_at: string;
  } | null;
  execution_duration_ms: number;
  created_at: string;
}

export interface ExtractedFieldValue {
  id: string;
  field_key: string;
  label: string;
  normalized_value: unknown;
  raw_text: string;
  data_type: string;
  extraction_method: string;
  score: number | null;
  confidence: number | null;
  confidence_explanation?: string | null;
  source_document_id: string;
  source_page_number: number;
  source_bounding_boxes?: Array<{
    x: number;
    y: number;
    width: number;
    height: number;
  }>;
  source_token_ids?: string[];
  evidence_node_id?: string | null;
  validation_status: string;
  warnings: string[];
}

export interface DocumentExtractionResult {
  document_id: string;
  processing_run_id: string;
  document_class: DocumentClass;
  schema_id: string;
  schema_version: string;
  fields: Record<string, ExtractedFieldValue>;
  validation_summary: Record<string, unknown>;
  execution_duration_ms: number;
  created_at: string;
}

export interface TextToken {
  id?: string;
  token_id?: string;
  raw_text?: string;
  text?: string;
  normalized_text?: string | null;
  confidence?: number | null;
  reading_order_index?: number;
  is_coordinate_uncertain?: boolean;
  coordinate_uncertainty_reason?: string | null;
  detected_script?: string | null;
  is_numeral_converted?: boolean;
  original_numeral_system?: string | null;
  original_raw_value?: string | null;
  is_uncertain?: boolean;
  uncertainty_reason?: string | null;
  normalization_form?: string | null;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  metadata?: Record<string, unknown>;
}

export interface TextLine {
  id: string;
  raw_text: string;
  normalized_text?: string | null;
  confidence?: number | null;
  reading_order_index?: number;
  dominant_script?: string | null;
  script_token_counts?: Record<string, number>;
  bounding_box?: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | null;
  tokens: TextToken[];
}

export interface ObservationDisagreement {
  primary_engine?: string | null;
  alternative_key: string;
  alternative_engine?: string | null;
  primary_char_count: number;
  alternative_char_count: number;
  char_count_delta: number;
  primary_token_count: number;
  alternative_token_count: number;
  token_count_delta: number;
  has_disagreement: boolean;
  disagreement_reasons: string[];
}

export interface AlternativeExtractionObservation {
  engine_name: string;
  extraction_method?: string;
  raw_text: string;
  normalized_text?: string | null;
  token_count?: number;
  line_count?: number;
  tokens?: TextToken[];
  lines?: TextLine[];
  confidence?: number | null;
  metadata?: Record<string, unknown>;
}

export interface ExtractedPageText {
  page_number: number;
  raw_text: string;
  normalized_text?: string;
  tokens: TextToken[];
  lines?: TextLine[];
  has_vector_text?: boolean;
  engine_name?: string;
  routing_decision?: string;
  routing_reason?: string | null;
  raster_area_ratio?: number | null;
  vector_char_count?: number | null;
  script_distribution?: Record<string, number>;
  alternative_extractions?: Record<string, AlternativeExtractionObservation>;
  disagreements?: ObservationDisagreement[];
  extraction_status: string;
  geometry?: {
    width: number;
    height: number;
    rotation: number;
    dpi?: number;
  };
}

export interface ExtractedDocumentText {
  schema_version?: string;
  document_id: string;
  processing_run_id: string;
  total_pages: number;
  total_tokens: number;
  full_raw_text: string;
  full_normalized_text?: string;
  script_summary?: Record<string, number>;
  pages: ExtractedPageText[];
}

export interface PageLayerSummary {
  page_number: number;
  routing_decision?: string | null;
  routing_reason?: string | null;
  raster_area_ratio?: number | null;
  vector_char_count?: number | null;
  has_vector_text?: boolean;
  script_distribution?: Record<string, number>;
  primary_engine?: string | null;
  primary_raw_text?: string;
  primary_normalized_text?: string;
  primary_token_count?: number;
  primary_confidence?: number | null;
  alternative_layers?: Record<string, unknown>;
  disagreements?: ObservationDisagreement[];
  potential_duplicates?: Array<Record<string, unknown>>;
}

export interface DocumentLayersResponse {
  document_id: string;
  processing_run_id: string;
  schema_version: string;
  script_summary?: Record<string, number>;
  total_pages: number;
  pages: PageLayerSummary[];
}

export interface DossierSection {
  section_id: string;
  title: string;
  order: number;
  content: string;
  items: Record<string, unknown>[];
}

export interface InvestigationDossier {
  id: string;
  case_id: string;
  title: string;
  scope_and_purpose?: string;
  version: number;
  status: DossierStatus;
  executive_summary?: string;
  sections?: DossierSection[];
  document_summaries?: Record<string, unknown>[];
  finding_ids?: string[];
  evidence_ids?: string[];
  review_decisions?: Record<string, unknown>[];
  limitations?: string[];
  unresolved_questions?: string[];
  content_hash?: string | null;
  dossier_payload?: Record<string, unknown>;
  created_at: string;
  finalized_at?: string | null;
  total_findings?: number;
  reviewed_findings_count?: number;
  dossier_reference?: string;
  integrity_hash?: string | null;
  updated_at?: string;
  created_by?: string;
}

export interface DossierGenerateRequest {
  created_by?: string;
  scope_and_purpose?: string | null;
}

export interface DossierFinalizeRequest {
  user_id: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

// ---------------------------------------------------------------------------
// Unified Evidence Graph Types (Phase 3C)
// ---------------------------------------------------------------------------

export type GraphNodeType =
  | "CASE"
  | "DOCUMENT"
  | "PERSON"
  | "ORGANIZATION"
  | "SUPPLIER"
  | "BUYER"
  | "MERCHANT"
  | "BANK"
  | "ACCOUNT"
  | "INVOICE"
  | "RECEIPT"
  | "PURCHASE_ORDER"
  | "BANK_TRANSACTION"
  | "EVIDENCE"
  | "FORENSIC_FINDING"
  | "CONSISTENCY_FINDING";

export type GraphRelationshipStatus =
  | "CONFIRMED"
  | "CANDIDATE"
  | "CONTRADICTED"
  | "UNRESOLVED"
  | "REJECTED";

export interface GraphNode {
  id: string;
  case_id: string;
  node_type: GraphNodeType;
  source_entity_type: string;
  source_entity_id: string;
  label: string;
  display_attributes: Record<string, unknown>;
  provenance: Record<string, unknown>;
  created_at: string | null;
}

export interface GraphEdge {
  id: string;
  case_id: string;
  source_node_id: string;
  target_node_id: string;
  predicate: string;
  status: GraphRelationshipStatus;
  status_determination_method: string | null;
  score: number | null;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
  source_relationship_id: string | null;
  explanation: string | null;
  metadata: Record<string, unknown>;
}

export interface GraphPath {
  nodes: GraphNode[];
  edges: GraphEdge[];
  length: number;
  is_confirmed_only: boolean;
}

export interface GraphSnapshot {
  case_id: string;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  truncated: boolean;
  query_metadata: Record<string, unknown>;
  projection_version: string;
}

export interface GraphNeighborhoodResult {
  case_id: string;
  center_node_id: string;
  hops: number;
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  truncated: boolean;
}

export interface GraphPathsResult {
  case_id: string;
  source_node_id: string;
  target_node_id: string;
  max_depth: number;
  paths: GraphPath[];
}

export type AssistantQuestionCategory =
  | "EVIDENCE_EXPLANATION"
  | "CROSS_DOCUMENT_COMPARISON"
  | "ENTITY_INVESTIGATION"
  | "CONTRADICTION_ANALYSIS"
  | "INVESTIGATION_SUMMARY"
  | "FOLLOW_UP_SUGGESTIONS"
  | "GENERAL_INQUIRY";

export interface EvidenceCitation {
  citation_id: string;
  case_id: string;
  document_id: string | null;
  document_title: string | null;
  evidence_id: string | null;
  finding_id: string | null;
  entity_id: string | null;
  relationship_id: string | null;
  source_subsystem: string;
  page_number: number | null;
  bounding_box: { x: number; y: number; width: number; height: number } | null;
  relevant_text: string | null;
  target_route: string | null;
}

export interface AssistantMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AssistantQueryRequest {
  question: string;
  conversation_context?: AssistantMessage[];
  explicit_evidence_ids?: string[];
  category_hint?: AssistantQuestionCategory;
  reviewer_id?: string;
}

export interface AssistantQueryResponse {
  case_id: string;
  question_category: AssistantQuestionCategory;
  answer_text: string;
  citations: EvidenceCitation[];
  observed_facts: string[];
  automated_indicators: string[];
  analytical_interpretations: string[];
  contradictory_evidence: string[];
  unresolved_questions: string[];
  limitations: string[];
  follow_up_suggestions: string[];
  has_sufficient_evidence: boolean;
  ai_notice: string;
  retrieval_stats: Record<string, unknown>;
  model_name: string;
}

export interface AssistantContextSummary {
  case_id: string;
  case_title: string;
  case_status: string;
  counts: {
    documents: number;
    forensic_findings: number;
    consistency_findings: number;
    entities: number;
    relationships: number;
    reviews: number;
    total_items: number;
  };
  document_titles: string[];
  unavailable_subsystems: string[];
}

export type CaseRole = "ADMIN" | "INVESTIGATOR" | "REVIEWER" | "VIEWER";
export type SystemRole = "SYSTEM_ADMIN" | "USER";

export interface User {
  id: string;
  email: string;
  username: string;
  full_name: string;
  is_active: boolean;
  system_role: SystemRole;
  created_at: string;
  updated_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface CaseMemberResponse {
  id: string;
  case_id: string;
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  role: CaseRole;
  assigned_by?: string | null;
  created_at: string;
}

