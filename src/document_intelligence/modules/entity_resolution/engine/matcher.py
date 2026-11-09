"""Deterministic entity comparison engine enforcing conservative matching and contradiction detection."""

from __future__ import annotations

from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    EntityMatchClassification,
    EntityMatchingMethod,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMatchEvidence,
    EntityMention,
)
from document_intelligence.modules.entity_resolution.engine.similarity import (
    compute_composite_name_similarity,
)


class DeterministicEntityMatcher:
    """Evaluates pairs of entity mentions with conservative evidentiary rules and contradiction checks."""

    def __init__(
        self,
        strong_similarity_threshold: float = 0.85,
        weak_similarity_threshold: float = 0.65,
    ) -> None:
        self.strong_threshold = strong_similarity_threshold
        self.weak_threshold = weak_similarity_threshold

    def compare_mentions(
        self,
        m1: EntityMention,
        m2: EntityMention,
        run_id: str,
    ) -> EntityCandidateMatch | None:
        """Compare two entity mentions and return an EntityCandidateMatch, or None if below minimal threshold.

        Guarantees:
        - Strict case isolation (SecurityException on cross-case comparison).
        - Distinct entity mentions only (skips self-comparison).
        - Different entity types are never matched.
        - Similarity is not identity: candidates are classified with explicit evidentiary semantics.
        """
        # 1. Enforce strict cross-case isolation
        if m1.case_id != m2.case_id:
            raise SecurityException(
                f"Cross-case entity resolution prohibited: '{m1.case_id}' vs '{m2.case_id}'."
            )

        # 2. Skip self-comparison
        if m1.mention_id == m2.mention_id:
            return None

        # 3. Only compare identical entity types
        if m1.entity_type != m2.entity_type:
            return None

        # Route comparison by entity type
        if m1.entity_type == ResolvedEntityType.TAX_IDENTIFIER:
            return self._compare_tax_identifiers(m1, m2, run_id)
        elif m1.entity_type in (
            ResolvedEntityType.INVOICE_REFERENCE,
            ResolvedEntityType.TRANSACTION_REFERENCE,
        ):
            return self._compare_references(m1, m2, run_id)
        elif m1.entity_type == ResolvedEntityType.BANK_ACCOUNT_REFERENCE:
            return self._compare_bank_accounts(m1, m2, run_id)
        elif m1.entity_type == ResolvedEntityType.CURRENCY_AMOUNT:
            return self._compare_currency_amounts(m1, m2, run_id)
        elif m1.entity_type == ResolvedEntityType.ORGANIZATION:
            return self._compare_organizations(m1, m2, run_id)
        elif m1.entity_type == ResolvedEntityType.PERSON:
            return self._compare_persons(m1, m2, run_id)

        return None

    def _build_evidence(
        self,
        m1: EntityMention,
        m2: EntityMention,
        matching_signals: list[str],
        contradicting_signals: list[str],
    ) -> EntityMatchEvidence:
        return EntityMatchEvidence(
            target_mention_id=m1.mention_id,
            candidate_mention_id=m2.mention_id,
            target_document_id=m1.document_id,
            candidate_document_id=m2.document_id,
            target_page_number=m1.page_number,
            candidate_page_number=m2.page_number,
            target_field_key=m1.field_key,
            candidate_field_key=m2.field_key,
            target_evidence_node_ids=m1.supporting_evidence_node_ids,
            candidate_evidence_node_ids=m2.supporting_evidence_node_ids,
            matching_signals=matching_signals,
            contradicting_signals=contradicting_signals,
            resolution_algorithm_version="1.0.0",
        )

    def _compare_tax_identifiers(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        # Check type/jurisdiction compatibility
        if m1.identifier_type and m2.identifier_type and m1.identifier_type != m2.identifier_type:
            contradicting_signals.append(
                f"Conflicting tax identifier types: '{m1.identifier_type}' vs '{m2.identifier_type}'."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
                match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
                match_score=0.0,
                score_semantics="Distinct tax identifier types cannot represent the same entity.",
                decision_status=MatchDecisionStatus.REJECTED,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        if m1.normalized_value == m2.normalized_value and m1.normalized_value != "":
            matching_signals.append(
                f"Exact tax identifier match ({m1.identifier_type or 'TAX_ID'}: {m1.normalized_value})."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.EXACT_IDENTIFIER,
                match_classification=EntityMatchClassification.EXACT_MATCH,
                match_score=1.0,
                score_semantics="Exact canonical tax identifier match.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        contradicting_signals.append("Different tax identifier values.")
        return EntityCandidateMatch(
            case_id=m1.case_id,
            processing_run_id=run_id,
            entity_type=m1.entity_type,
            target_mention_id=m1.mention_id,
            candidate_mention_id=m2.mention_id,
            target_value_display=m1.normalized_value,
            candidate_value_display=m2.normalized_value,
            matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
            match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
            match_score=0.0,
            score_semantics="Contradicting tax identifiers for same type.",
            decision_status=MatchDecisionStatus.REJECTED,
            evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
        )

    def _compare_references(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch | None:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        if m1.normalized_value == m2.normalized_value and m1.normalized_value != "":
            matching_signals.append(f"Exact normalized reference match ({m1.normalized_value}).")
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.EXACT_REFERENCE,
                match_classification=EntityMatchClassification.EXACT_MATCH,
                match_score=1.0,
                score_semantics="Exact normalized reference string match preserving leading zeros.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        # Check leading zero variance (e.g. '00123' vs '123')
        if (
            m1.normalized_value.lstrip("0") == m2.normalized_value.lstrip("0")
            and m1.normalized_value.lstrip("0") != ""
        ):
            matching_signals.append("Reference match when stripping leading zeros.")
            contradicting_signals.append("Leading zero formatting variance detected.")
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.RULE_FALLBACK,
                match_classification=EntityMatchClassification.STRONG_CANDIDATE,
                match_score=0.85,
                score_semantics="Reference match subject to leading-zero formatting discrepancy.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        return None

    def _compare_bank_accounts(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        if m1.normalized_value == m2.normalized_value and m1.normalized_value != "****":
            matching_signals.append(f"Matching masked account digits ({m1.normalized_value}).")
            contradicting_signals.append(
                "Masked last-4 digits alone provide weak evidence of account identity due to collision probability."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.EXACT_REFERENCE,
                match_classification=EntityMatchClassification.WEAK_AMBIGUOUS,
                match_score=0.40,
                score_semantics="Masked account match represents weak probabilistic coincidence.",
                decision_status=MatchDecisionStatus.AMBIGUOUS,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        contradicting_signals.append("Contradictory masked account numbers.")
        return EntityCandidateMatch(
            case_id=m1.case_id,
            processing_run_id=run_id,
            entity_type=m1.entity_type,
            target_mention_id=m1.mention_id,
            candidate_mention_id=m2.mention_id,
            target_value_display=m1.normalized_value,
            candidate_value_display=m2.normalized_value,
            matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
            match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
            match_score=0.0,
            score_semantics="Distinct masked account digits.",
            decision_status=MatchDecisionStatus.REJECTED,
            evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
        )

    def _compare_currency_amounts(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch | None:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        # Currency mismatch check
        if m1.currency_code != m2.currency_code:
            contradicting_signals.append(
                f"Currency mismatch: '{m1.currency_code}' vs '{m2.currency_code}'."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
                match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
                match_score=0.0,
                score_semantics="Amounts across different currencies cannot be matched as identical.",
                decision_status=MatchDecisionStatus.REJECTED,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        if m1.currency_code == "UNKNOWN" or m2.currency_code == "UNKNOWN":
            contradicting_signals.append(
                "Unknown currency code prevents confirmed monetary identity."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.RULE_FALLBACK,
                match_classification=EntityMatchClassification.INSUFFICIENT_EVIDENCE,
                match_score=0.30,
                score_semantics="Unknown currency prevents confident monetary resolution.",
                decision_status=MatchDecisionStatus.AMBIGUOUS,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        if m1.numeric_amount is not None and m1.numeric_amount == m2.numeric_amount:
            matching_signals.append(
                f"Exact monetary amount equality ({m1.currency_code} {m1.numeric_amount})."
            )
            matching_signals.append(
                "NOTE: Amount coincidence alone does not establish legal transaction identity."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.NORMALIZED_EXACT,
                match_classification=EntityMatchClassification.NORMALIZED_EXACT_MATCH,
                match_score=0.95,
                score_semantics="Exact Decimal equality respecting ISO 4217 minor units.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        return None

    def _compare_organizations(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch | None:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        # Contradiction check: explicit tax IDs differ
        tax1 = m1.metadata.get("tax_id")
        tax2 = m2.metadata.get("tax_id")
        if tax1 and tax2 and tax1 != tax2:
            contradicting_signals.append(
                f"Conflicting tax identifiers associated with organizations: '{tax1}' vs '{tax2}'."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.CONTRADICTION_DETECTED,
                match_classification=EntityMatchClassification.CONFLICTING_IDENTITY,
                match_score=0.10,
                score_semantics="Organizations with differing explicit tax IDs cannot be resolved as identical.",
                decision_status=MatchDecisionStatus.REJECTED,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        # 1. Exact normalized match
        if m1.normalized_value == m2.normalized_value and m1.normalized_value != "":
            matching_signals.append(
                f"Exact normalized organization name match ('{m1.normalized_value}')."
            )
            if m1.legal_suffix:
                matching_signals.append(f"Matching legal suffix ('{m1.legal_suffix}').")

            # Check if composite signals (e.g. shared invoice reference or shared tax id) exist
            shared_ref = m1.metadata.get("invoice_number") and (
                m1.metadata.get("invoice_number") == m2.metadata.get("invoice_number")
            )
            if shared_ref:
                matching_signals.append(
                    f"Shared invoice reference: '{m1.metadata.get('invoice_number')}'."
                )

            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.COMPOSITE_SIGNALS
                if shared_ref
                else EntityMatchingMethod.NORMALIZED_EXACT,
                match_classification=EntityMatchClassification.NORMALIZED_EXACT_MATCH,
                match_score=0.98,
                score_semantics="Exact normalized organization string match.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        # 2. Base name match with legal suffix comparison
        if m1.base_name and m2.base_name and m1.base_name == m2.base_name:
            matching_signals.append(f"Identical base name ('{m1.base_name}').")
            if m1.legal_suffix != m2.legal_suffix and m1.legal_suffix and m2.legal_suffix:
                contradicting_signals.append(
                    f"Conflicting legal suffixes: '{m1.legal_suffix}' vs '{m2.legal_suffix}'."
                )
                return EntityCandidateMatch(
                    case_id=m1.case_id,
                    processing_run_id=run_id,
                    entity_type=m1.entity_type,
                    target_mention_id=m1.mention_id,
                    candidate_mention_id=m2.mention_id,
                    target_value_display=m1.normalized_value,
                    candidate_value_display=m2.normalized_value,
                    matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
                    match_classification=EntityMatchClassification.WEAK_AMBIGUOUS,
                    match_score=0.65,
                    score_semantics="Base names match but explicit legal suffixes contradict.",
                    decision_status=MatchDecisionStatus.AMBIGUOUS,
                    evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
                )
            else:
                matching_signals.append("Legal suffix variance compatible.")
                return EntityCandidateMatch(
                    case_id=m1.case_id,
                    processing_run_id=run_id,
                    entity_type=m1.entity_type,
                    target_mention_id=m1.mention_id,
                    candidate_mention_id=m2.mention_id,
                    target_value_display=m1.normalized_value,
                    candidate_value_display=m2.normalized_value,
                    matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
                    match_classification=EntityMatchClassification.STRONG_CANDIDATE,
                    match_score=0.90,
                    score_semantics="Identical base name with minor legal suffix difference.",
                    decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                    evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
                )

        # 3. String & Token similarity
        sim = compute_composite_name_similarity(m1.normalized_value, m2.normalized_value)
        if sim >= self.strong_threshold:
            matching_signals.append(f"High composite name similarity ratio: {sim:.2f}.")
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
                match_classification=EntityMatchClassification.STRONG_CANDIDATE,
                match_score=sim,
                score_semantics="Deterministic composite character and token similarity score.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )
        elif sim >= self.weak_threshold:
            matching_signals.append(f"Moderate name similarity ratio: {sim:.2f}.")
            contradicting_signals.append(
                "Name similarity alone does not establish organizational identity."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.ORGANIZATION_NAME_SIMILARITY,
                match_classification=EntityMatchClassification.WEAK_AMBIGUOUS,
                match_score=sim,
                score_semantics="Moderate similarity; requires human review or corroborating evidence.",
                decision_status=MatchDecisionStatus.AMBIGUOUS,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        return None

    def _compare_persons(
        self, m1: EntityMention, m2: EntityMention, run_id: str
    ) -> EntityCandidateMatch | None:
        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        if m1.normalized_value == m2.normalized_value and m1.normalized_value != "":
            matching_signals.append(
                f"Exact normalized person name match ('{m1.normalized_value}')."
            )
            contradicting_signals.append(
                "Similarity is not identity: distinct individuals may share identical names without unique identifiers."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.NORMALIZED_EXACT,
                match_classification=EntityMatchClassification.STRONG_CANDIDATE,
                match_score=0.85,
                score_semantics="Deterministic person name equality. Requires contextual or identifier corroboration.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        sim = compute_composite_name_similarity(m1.normalized_value, m2.normalized_value)
        if sim >= self.strong_threshold:
            matching_signals.append(f"High person name similarity ratio: {sim:.2f}.")
            contradicting_signals.append(
                "Name similarity alone does not confirm personal identity."
            )
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.PERSON_NAME_SIMILARITY,
                match_classification=EntityMatchClassification.STRONG_CANDIDATE,
                match_score=sim,
                score_semantics="Deterministic string and token similarity ratio.",
                decision_status=MatchDecisionStatus.ALGORITHMIC_CANDIDATE,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )
        elif sim >= self.weak_threshold:
            matching_signals.append(f"Moderate person name similarity ratio: {sim:.2f}.")
            contradicting_signals.append("Insufficient distinctiveness to assert identity.")
            return EntityCandidateMatch(
                case_id=m1.case_id,
                processing_run_id=run_id,
                entity_type=m1.entity_type,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_value_display=m1.normalized_value,
                candidate_value_display=m2.normalized_value,
                matching_method=EntityMatchingMethod.PERSON_NAME_SIMILARITY,
                match_classification=EntityMatchClassification.WEAK_AMBIGUOUS,
                match_score=sim,
                score_semantics="Weak similarity; ambiguous match.",
                decision_status=MatchDecisionStatus.AMBIGUOUS,
                evidence=self._build_evidence(m1, m2, matching_signals, contradicting_signals),
            )

        return None
