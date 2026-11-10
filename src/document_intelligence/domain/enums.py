"""Domain enumeration types defining core lifecycles and categories."""

from enum import StrEnum


class CaseStatus(StrEnum):
    """Lifecycle states for an investigation Case workspace."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    UNDER_REVIEW = "UNDER_REVIEW"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class DocumentClass(StrEnum):
    """Core document classification categories for intelligence and extraction."""

    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    BANK_STATEMENT = "BANK_STATEMENT"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    TAX_DOCUMENT = "TAX_DOCUMENT"
    CONTRACT = "CONTRACT"
    UNKNOWN = "UNKNOWN"


class DocumentType(StrEnum):
    """Classification types for uploaded documents."""

    UNKNOWN = "UNKNOWN"
    PAYSTUB = "PAYSTUB"
    BANK_STATEMENT = "BANK_STATEMENT"
    ID_CARD = "ID_CARD"
    PASSPORT = "PASSPORT"
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    IDENTITY_DOCUMENT = "IDENTITY_DOCUMENT"
    TAX_DOCUMENT = "TAX_DOCUMENT"
    CONTRACT = "CONTRACT"
    TAX_RETURN = "TAX_RETURN"


class FieldDataType(StrEnum):
    """Data types for structured field extraction."""

    STRING = "STRING"
    NUMBER = "NUMBER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    CURRENCY = "CURRENCY"
    BOOLEAN = "BOOLEAN"
    MASKED_STRING = "MASKED_STRING"


class FieldValidationStatus(StrEnum):
    """Validation outcome for an individual extracted field."""

    VALID = "VALID"
    INVALID = "INVALID"
    UNVALIDATED = "UNVALIDATED"
    WARNING = "WARNING"


class IngestionStatus(StrEnum):
    """Ingestion and storage lifecycle status for a document."""

    PENDING = "PENDING"
    STORED = "STORED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class PipelineStatus(StrEnum):
    """Execution status for an analysis or forensic processing run."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIALLY_SUCCEEDED = "PARTIALLY_SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EvidenceType(StrEnum):
    """Classification of an atomic piece of forensic evidence."""

    OCR_TEXT = "OCR_TEXT"
    EXTRACTED_FIELD = "EXTRACTED_FIELD"
    DOCUMENT_PAGE = "DOCUMENT_PAGE"
    LAYOUT_REGION = "LAYOUT_REGION"
    TABLE = "TABLE"
    TABLE_CELL = "TABLE_CELL"
    TEXT_LINE = "TEXT_LINE"
    TEXT_TOKEN = "TEXT_TOKEN"
    VISUAL_REGION = "VISUAL_REGION"
    PDF_STRUCTURAL = "PDF_STRUCTURAL"
    METADATA = "METADATA"
    CROSS_DOCUMENT = "CROSS_DOCUMENT"
    RULE_VALIDATION = "RULE_VALIDATION"
    REVIEW_ANNOTATION = "REVIEW_ANNOTATION"
    ENTITY_MENTION = "ENTITY_MENTION"
    RESOLVED_ENTITY = "RESOLVED_ENTITY"
    RELATIONSHIP_EVIDENCE = "RELATIONSHIP_EVIDENCE"
    CONSISTENCY_COMPARISON = "CONSISTENCY_COMPARISON"


class LayoutRegionType(StrEnum):
    """Semantic region types for document layout parsing."""

    HEADER = "HEADER"
    FOOTER = "FOOTER"
    TITLE = "TITLE"
    PARAGRAPH = "PARAGRAPH"
    TABLE = "TABLE"
    FIGURE = "FIGURE"
    CAPTION = "CAPTION"
    LIST = "LIST"
    KEY_VALUE = "KEY_VALUE"
    UNKNOWN = "UNKNOWN"


class CoordinateSystem(StrEnum):
    """Coordinate system used for bounding boxes."""

    NORMALIZED_0_1 = "NORMALIZED_0_1"  # 0.0 to 1.0 relative to page width and height
    PIXEL_EXACT = "PIXEL_EXACT"  # Exact raster pixel dimensions
    PDF_POINTS = "PDF_POINTS"  # 1/72 inch native PDF coordinates


class ScriptType(StrEnum):
    """Writing script system classified for a token, line, or document."""

    DEVANAGARI = "DEVANAGARI"
    LATIN = "LATIN"
    NUMERIC = "NUMERIC"
    MIXED = "MIXED"
    PUNCTUATION = "PUNCTUATION"
    UNKNOWN = "UNKNOWN"


class PageRoutingDecision(StrEnum):
    """Routing decisions for page-level extraction engine dispatch."""

    # Canonical Phase 4D.3.1 & 4D.3.4 outcomes
    NO_TEXT = "NO_TEXT"
    VECTOR_ONLY = "VECTOR_ONLY"
    OCR_ONLY = "OCR_ONLY"
    HYBRID_FUSION = "HYBRID_FUSION"
    OPTICAL_OCR = "OPTICAL_OCR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    PROCESSING_FAILED = "PROCESSING_FAILED"

    # Legacy aliases (preserved for backward compatibility with historical records)
    DIGITAL_VECTOR_PRIMARY = "DIGITAL_VECTOR_PRIMARY"
    IMAGE_ONLY_SCANNED_PAGE = "IMAGE_ONLY_SCANNED_PAGE"
    SPARSE_TEXT_FALLBACK = "SPARSE_TEXT_FALLBACK"
    FORCED_OPTICAL_OCR = "FORCED_OPTICAL_OCR"
    DIRECT_IMAGE_OPTICAL_OCR = "DIRECT_IMAGE_OPTICAL_OCR"
    FAILED = "FAILED"


class NormalizationForm(StrEnum):
    """Unicode normalization forms and standards."""

    NFC = "NFC"
    NFD = "NFD"
    NFKC = "NFKC"
    NFKD = "NFKD"


class FindingCategory(StrEnum):
    """Categories of forensic findings or anomalies."""

    PDF_STRUCTURE = "PDF_STRUCTURE"
    VISUAL_ANOMALY = "VISUAL_ANOMALY"
    DOCUMENT_INCONSISTENCY = "DOCUMENT_INCONSISTENCY"
    FINANCIAL_VALIDATION = "FINANCIAL_VALIDATION"
    IDENTITY_VALIDATION = "IDENTITY_VALIDATION"
    CROSS_DOCUMENT_MISMATCH = "CROSS_DOCUMENT_MISMATCH"
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"
    OTHER = "OTHER"


class FindingSeverity(StrEnum):
    """Assessed severity of a forensic finding.

    NOTE: Severity indicates evidentiary significance, NOT confirmed fraud probability.
    """

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingStatus(StrEnum):
    """Investigation status of a forensic finding."""

    DETECTED = "DETECTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED_OBSERVATION = "CONFIRMED_OBSERVATION"
    DISMISSED = "DISMISSED"
    RESOLVED = "RESOLVED"


class DossierStatus(StrEnum):
    """Lifecycle status of an investigation dossier."""

    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ReviewDecisionType(StrEnum):
    """Investigator review decision on a finding or dossier."""

    ACCEPT = "ACCEPT"
    DISMISS = "DISMISS"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"
    ESCALATE = "ESCALATE"


class AuditEventType(StrEnum):
    """Types of auditable actions recorded in the immutable provenance ledger."""

    CASE_CREATED = "CASE_CREATED"
    CASE_STATUS_CHANGED = "CASE_STATUS_CHANGED"
    DOCUMENT_INGESTED = "DOCUMENT_INGESTED"
    FILE_HASH_REGISTERED = "FILE_HASH_REGISTERED"
    ANALYSIS_REQUESTED = "ANALYSIS_REQUESTED"
    PROCESSING_RUN_STARTED = "PROCESSING_RUN_STARTED"
    PROCESSING_RUN_COMPLETED = "PROCESSING_RUN_COMPLETED"
    PROCESSING_RUN_INTERRUPTED = "PROCESSING_RUN_INTERRUPTED"
    INTEGRITY_VERIFICATION_FAILED = "INTEGRITY_VERIFICATION_FAILED"
    FINDING_CREATED = "FINDING_CREATED"
    FINDING_STATUS_CHANGED = "FINDING_STATUS_CHANGED"
    REVIEW_DECISION_RECORDED = "REVIEW_DECISION_RECORDED"
    DOSSIER_CREATED = "DOSSIER_CREATED"
    DOSSIER_APPROVED = "DOSSIER_APPROVED"
    EXPORT_GENERATED = "EXPORT_GENERATED"
    DOCUMENT_CLASSIFIED = "DOCUMENT_CLASSIFIED"
    DOCUMENT_CLASSIFICATION_OVERRIDDEN = "DOCUMENT_CLASSIFICATION_OVERRIDDEN"
    FIELDS_EXTRACTED = "FIELDS_EXTRACTED"
    EXTRACTION_VALIDATED = "EXTRACTION_VALIDATED"
    ENTITIES_RESOLVED = "ENTITIES_RESOLVED"
    ENTITY_MATCH_REVIEWED = "ENTITY_MATCH_REVIEWED"
    RELATIONSHIPS_DETECTED = "RELATIONSHIPS_DETECTED"
    RELATIONSHIP_REVIEWED = "RELATIONSHIP_REVIEWED"
    CONSISTENCY_ANALYSIS_REQUESTED = "CONSISTENCY_ANALYSIS_REQUESTED"
    CONSISTENCY_ANALYSIS_COMPLETED = "CONSISTENCY_ANALYSIS_COMPLETED"
    CONSISTENCY_FINDING_REVIEWED = "CONSISTENCY_FINDING_REVIEWED"
    DOSSIER_FINALIZED = "DOSSIER_FINALIZED"
    ASSISTANT_QUERY_EXECUTED = "ASSISTANT_QUERY_EXECUTED"
    CROSS_CASE_SCOPE_CREATED = "CROSS_CASE_SCOPE_CREATED"
    CROSS_CASE_SCOPE_MODIFIED = "CROSS_CASE_SCOPE_MODIFIED"
    CROSS_CASE_CORRELATION_EXECUTED = "CROSS_CASE_CORRELATION_EXECUTED"
    CROSS_CASE_CANDIDATE_REVIEWED = "CROSS_CASE_CANDIDATE_REVIEWED"


class EntityType(StrEnum):
    """Types of domain entities subject to auditing."""

    CASE = "CASE"
    DOCUMENT = "DOCUMENT"
    PROCESSING_RUN = "PROCESSING_RUN"
    EVIDENCE_NODE = "EVIDENCE_NODE"
    FORENSIC_FINDING = "FORENSIC_FINDING"
    DOSSIER = "DOSSIER"
    REVIEW_DECISION = "REVIEW_DECISION"
    ENTITY_MATCH = "ENTITY_MATCH"
    RESOLVED_ENTITY = "RESOLVED_ENTITY"
    RELATIONSHIP = "RELATIONSHIP"
    CONSISTENCY_RUN = "CONSISTENCY_RUN"
    CONSISTENCY_FINDING = "CONSISTENCY_FINDING"
    CONSISTENCY_REVIEW = "CONSISTENCY_REVIEW"
    AGGREGATED_FINDING = "AGGREGATED_FINDING"
    ASSISTANT_SESSION = "ASSISTANT_SESSION"


class ResolvedEntityType(StrEnum):
    """Types of real-world entities extracted and resolved across documents."""

    ORGANIZATION = "ORGANIZATION"
    PERSON = "PERSON"
    TAX_IDENTIFIER = "TAX_IDENTIFIER"
    INVOICE_REFERENCE = "INVOICE_REFERENCE"
    BANK_ACCOUNT_REFERENCE = "BANK_ACCOUNT_REFERENCE"
    CURRENCY_AMOUNT = "CURRENCY_AMOUNT"
    TRANSACTION_REFERENCE = "TRANSACTION_REFERENCE"


class EntityMatchClassification(StrEnum):
    """Evidentiary classification of an entity candidate match."""

    EXACT_MATCH = "EXACT_MATCH"
    NORMALIZED_EXACT_MATCH = "NORMALIZED_EXACT_MATCH"
    STRONG_CANDIDATE = "STRONG_CANDIDATE"
    WEAK_AMBIGUOUS = "WEAK_AMBIGUOUS"
    CONFLICTING_IDENTITY = "CONFLICTING_IDENTITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class MatchDecisionStatus(StrEnum):
    """Current state of an entity match decision."""

    ALGORITHMIC_CANDIDATE = "ALGORITHMIC_CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


class HumanReviewStatus(StrEnum):
    """Review status indicating whether human judgment has been applied."""

    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    AMBIGUOUS = "AMBIGUOUS"


class EntityReviewAction(StrEnum):
    """Available human review actions on a candidate match."""

    CONFIRM_MATCH = "CONFIRM_MATCH"
    REJECT_MATCH = "REJECT_MATCH"
    MARK_AMBIGUOUS = "MARK_AMBIGUOUS"


class EntityMatchingMethod(StrEnum):
    """Deterministic matching strategy applied to compare mentions."""

    EXACT_IDENTIFIER = "EXACT_IDENTIFIER"
    EXACT_REFERENCE = "EXACT_REFERENCE"
    NORMALIZED_EXACT = "NORMALIZED_EXACT"
    ORGANIZATION_NAME_SIMILARITY = "ORGANIZATION_NAME_SIMILARITY"
    PERSON_NAME_SIMILARITY = "PERSON_NAME_SIMILARITY"
    COMPOSITE_SIGNALS = "COMPOSITE_SIGNALS"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    RULE_FALLBACK = "RULE_FALLBACK"


class RelationshipType(StrEnum):
    """Types of cross-document, entity, and financial relationships.

    Ontology Version 2.0 (Phase 2C.3.2.1): Directed Subject-Predicate-Object semantics.
    """

    # V2 Directed Predicates (Subject --Predicate--> Object)
    ISSUED = "ISSUED"  # Supplier/Merchant/Bank --ISSUED--> Document
    BILLED_TO = "BILLED_TO"  # Invoice --BILLED_TO--> Buyer
    INVOICED = "INVOICED"  # Supplier --INVOICED--> Buyer (single billing event)
    REFERENCES_PURCHASE_ORDER = (
        "REFERENCES_PURCHASE_ORDER"  # Invoice --REFERENCES_PURCHASE_ORDER--> PO
    )
    REFERENCES_INVOICE = "REFERENCES_INVOICE"  # Receipt --REFERENCES_INVOICE--> Invoice
    REFERENCES_RECEIPT = "REFERENCES_RECEIPT"
    SUPPORTS_DOCUMENT = "SUPPORTS_DOCUMENT"  # Document --SUPPORTS_DOCUMENT--> Document
    DUPLICATE_OF = "DUPLICATE_OF"  # Document --DUPLICATE_OF--> Document
    AMENDS_DOCUMENT = "AMENDS_DOCUMENT"  # Document --AMENDS_DOCUMENT--> Document
    RECORDS_PAYMENT = "RECORDS_PAYMENT"  # Receipt --RECORDS_PAYMENT--> Payment/Tx
    CONTAINS_TRANSACTION = (
        "CONTAINS_TRANSACTION"  # Bank Statement --CONTAINS_TRANSACTION--> Transaction
    )
    MAY_SETTLE = "MAY_SETTLE"  # Transaction --MAY_SETTLE--> Invoice
    REFUNDS = "REFUNDS"
    TRANSFERS_TO = "TRANSFERS_TO"
    HELD_BY = "HELD_BY"  # Account --HELD_BY--> Account Holder
    REPRESENTS = "REPRESENTS"  # Person --REPRESENTS--> Organization
    SUPPLIES = "SUPPLIES"  # Explicit ongoing supply contract/arrangement ONLY
    CUSTOMER_OF = "CUSTOMER_OF"  # Explicit customer relationship evidence ONLY

    # Legacy V1 aliases (preserved for reading historical records without desync)
    ISSUED_BY = "ISSUED_BY"
    ISSUED_TO = "ISSUED_TO"
    ACCOUNT_HELD_BY = "ACCOUNT_HELD_BY"


class DuplicateKind(StrEnum):
    """Specific evidentiary classification for duplicate document candidates."""

    BYTE_IDENTICAL = "BYTE_IDENTICAL"
    VISUALLY_SIMILAR = "VISUALLY_SIMILAR"
    SEMANTICALLY_SIMILAR = "SEMANTICALLY_SIMILAR"
    UNRESOLVED_DUPLICATE_CANDIDATE = "UNRESOLVED_DUPLICATE_CANDIDATE"


class StatusDeterminationMethod(StrEnum):
    """Method used to determine the final relationship status."""

    EVIDENTIARY_RULE = "EVIDENTIARY_RULE"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class RelationshipStatus(StrEnum):
    """Evidentiary state of a detected relationship.

    CONFIRMED indicates confirmation by explicit source statement or human review,
    not that the platform has independently established real-world ontological truth.
    """

    CONFIRMED = "CONFIRMED"
    CANDIDATE = "CANDIDATE"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    REJECTED = "REJECTED"


class RelationshipReviewAction(StrEnum):
    """Available human review actions on a detected relationship."""

    CONFIRM_RELATIONSHIP = "CONFIRM_RELATIONSHIP"
    REJECT_RELATIONSHIP = "REJECT_RELATIONSHIP"
    MARK_UNRESOLVED = "MARK_UNRESOLVED"


class RelationshipDetectionMethod(StrEnum):
    """Deterministic method used to discover a relationship."""

    EXPLICIT_FIELD_REFERENCE = "EXPLICIT_FIELD_REFERENCE"
    EXPLICIT_DOCUMENT_REFERENCE = "EXPLICIT_DOCUMENT_REFERENCE"
    DOCUMENT_HASH_EQUALITY = "DOCUMENT_HASH_EQUALITY"
    DOCUMENT_HASH_MATCH = "DOCUMENT_HASH_MATCH"  # Legacy V1 alias
    BYTE_EQUALITY_VERIFICATION = "BYTE_EQUALITY_VERIFICATION"
    MULTI_SIGNAL_ENTITY_MATCH = "MULTI_SIGNAL_ENTITY_MATCH"
    TRANSACTION_SETTLEMENT_RULE = "TRANSACTION_SETTLEMENT_RULE"
    PAYMENT_REFERENCE_RULE = "PAYMENT_REFERENCE_RULE"
    ROLE_REPRESENTATION_RULE = "ROLE_REPRESENTATION_RULE"
    COMMERCIAL_FLOW_RULE = "COMMERCIAL_FLOW_RULE"
    INVOICE_BILLING_EVENT_RULE = "INVOICE_BILLING_EVENT_RULE"
    CONTRACT_CLAUSE_RULE = "CONTRACT_CLAUSE_RULE"
    AMOUNT_COINCIDENCE_HEURISTIC = "AMOUNT_COINCIDENCE_HEURISTIC"
    VISUAL_SIMILARITY_HEURISTIC = "VISUAL_SIMILARITY_HEURISTIC"
    SEMANTIC_SIMILARITY_HEURISTIC = "SEMANTIC_SIMILARITY_HEURISTIC"


class ConsistencyOutcome(StrEnum):
    """Evidentiary outcome of a deterministic consistency comparison.

    These represent analytical check outcomes, NOT judicial fraud determinations.
    """

    CONSISTENT = "CONSISTENT"
    INCONSISTENT = "INCONSISTENT"
    POTENTIAL_ANOMALY = "POTENTIAL_ANOMALY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConsistencyReviewAction(StrEnum):
    """Available human reviewer actions for a cross-document consistency finding."""

    CONFIRM_INCONSISTENCY = "CONFIRM_INCONSISTENCY"
    DISMISS = "DISMISS"
    MARK_INSUFFICIENT_EVIDENCE = "MARK_INSUFFICIENT_EVIDENCE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class ConsistencyDetectionMethod(StrEnum):
    """Deterministic method used to evaluate cross-document consistency."""

    DETERMINISTIC_FIELD_COMPARISON = "DETERMINISTIC_FIELD_COMPARISON"
    MONETARY_RECONCILIATION_CHECK = "MONETARY_RECONCILIATION_CHECK"
    IDENTITY_RECORD_ALIGNMENT = "IDENTITY_RECORD_ALIGNMENT"
    TEMPORAL_SEQUENCE_CHECK = "TEMPORAL_SEQUENCE_CHECK"
    DUPLICATE_RECORD_ANALYSIS = "DUPLICATE_RECORD_ANALYSIS"
    CROSS_DOCUMENT_CROSS_CHECK = "CROSS_DOCUMENT_CROSS_CHECK"


class GraphNodeType(StrEnum):
    """Standardized node types supported in the unified Evidence Graph."""

    CASE = "CASE"
    DOCUMENT = "DOCUMENT"
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    SUPPLIER = "SUPPLIER"
    BUYER = "BUYER"
    MERCHANT = "MERCHANT"
    BANK = "BANK"
    ACCOUNT = "ACCOUNT"
    INVOICE = "INVOICE"
    RECEIPT = "RECEIPT"
    PURCHASE_ORDER = "PURCHASE_ORDER"
    BANK_TRANSACTION = "BANK_TRANSACTION"
    EVIDENCE = "EVIDENCE"
    FORENSIC_FINDING = "FORENSIC_FINDING"
    CONSISTENCY_FINDING = "CONSISTENCY_FINDING"


class GraphEdgePredicate(StrEnum):
    """Standardized relationship predicates in the unified Evidence Graph."""

    # Structural & Evidence Provenance Predicates
    CONTAINS_DOCUMENT = "CONTAINS_DOCUMENT"
    HAS_EVIDENCE = "HAS_EVIDENCE"
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    PERTAINS_TO = "PERTAINS_TO"
    COMPARES_DOCUMENT = "COMPARES_DOCUMENT"
    EXTRACTED_FROM = "EXTRACTED_FROM"
    MATCHES_IDENTITY = "MATCHES_IDENTITY"

    # Canonical V2 Domain Ontology Predicates (Subject --Predicate--> Object)
    ISSUED = "ISSUED"
    BILLED_TO = "BILLED_TO"
    INVOICED = "INVOICED"
    REFERENCES_PURCHASE_ORDER = "REFERENCES_PURCHASE_ORDER"
    REFERENCES_INVOICE = "REFERENCES_INVOICE"
    REFERENCES_RECEIPT = "REFERENCES_RECEIPT"
    SUPPORTS_DOCUMENT = "SUPPORTS_DOCUMENT"
    DUPLICATE_OF = "DUPLICATE_OF"
    AMENDS_DOCUMENT = "AMENDS_DOCUMENT"
    RECORDS_PAYMENT = "RECORDS_PAYMENT"
    CONTAINS_TRANSACTION = "CONTAINS_TRANSACTION"
    MAY_SETTLE = "MAY_SETTLE"
    REFUNDS = "REFUNDS"
    TRANSFERS_TO = "TRANSFERS_TO"
    HELD_BY = "HELD_BY"
    REPRESENTS = "REPRESENTS"
    SUPPLIES = "SUPPLIES"
    CUSTOMER_OF = "CUSTOMER_OF"

    # Cross-Case Intelligence Predicates
    CORRELATES_WITH = "CORRELATES_WITH"
    CROSS_CASE_CANDIDATE = "CROSS_CASE_CANDIDATE"
    POTENTIAL_DUPLICATE = "POTENTIAL_DUPLICATE"
    SHARED_IDENTIFIER = "SHARED_IDENTIFIER"

    # Legacy Aliases
    ISSUED_BY = "ISSUED_BY"
    ISSUED_TO = "ISSUED_TO"
    ACCOUNT_HELD_BY = "ACCOUNT_HELD_BY"


class CrossCaseReviewDecision(StrEnum):
    """Lifecycle decisions recorded on cross-case correlation candidates."""

    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    NEEDS_FURTHER_INVESTIGATION = "NEEDS_FURTHER_INVESTIGATION"


class AggregatedFindingCategory(StrEnum):
    """Unified categories for cross-domain investigation findings."""

    DOCUMENT_INTEGRITY = "DOCUMENT_INTEGRITY"
    VISUAL_ANOMALY = "VISUAL_ANOMALY"
    STRUCTURAL_ANOMALY = "STRUCTURAL_ANOMALY"
    EXTRACTION_ANOMALY = "EXTRACTION_ANOMALY"
    CROSS_DOCUMENT_INCONSISTENCY = "CROSS_DOCUMENT_INCONSISTENCY"
    ENTITY_IDENTITY_CONFLICT = "ENTITY_IDENTITY_CONFLICT"
    RELATIONSHIP_ANOMALY = "RELATIONSHIP_ANOMALY"
    DUPLICATE_OR_CONFLICTING_RECORD = "DUPLICATE_OR_CONFLICTING_RECORD"
    OTHER = "OTHER"


class EvidentiaryClassification(StrEnum):
    """Epistemic classification distinguishing fact, algorithmic signal, interpretation, and verdict."""

    OBSERVED_FACT = "OBSERVED_FACT"
    AUTOMATED_INDICATOR = "AUTOMATED_INDICATOR"
    ANALYTICAL_INTERPRETATION = "ANALYTICAL_INTERPRETATION"
    INVESTIGATOR_CONCLUSION = "INVESTIGATOR_CONCLUSION"


class InvestigatorReviewAction(StrEnum):
    """Actions available to human investigators reviewing aggregated findings."""

    MARK_NEEDS_REVIEW = "MARK_NEEDS_REVIEW"
    CONFIRM_OBSERVATION = "CONFIRM_OBSERVATION"
    DISMISS_FALSE_POSITIVE = "DISMISS_FALSE_POSITIVE"
    MARK_INCONCLUSIVE = "MARK_INCONCLUSIVE"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"


class DossierFormat(StrEnum):
    """Supported export formats for investigation evidence dossiers."""

    PDF = "PDF"
    JSON = "JSON"


class AssistantQuestionCategory(StrEnum):
    """Supported question and analysis categories for the Grounded AI Investigation Assistant."""

    EVIDENCE_EXPLANATION = "EVIDENCE_EXPLANATION"
    CROSS_DOCUMENT_COMPARISON = "CROSS_DOCUMENT_COMPARISON"
    ENTITY_INVESTIGATION = "ENTITY_INVESTIGATION"
    CONTRADICTION_ANALYSIS = "CONTRADICTION_ANALYSIS"
    INVESTIGATION_SUMMARY = "INVESTIGATION_SUMMARY"
    FOLLOW_UP_SUGGESTIONS = "FOLLOW_UP_SUGGESTIONS"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"
