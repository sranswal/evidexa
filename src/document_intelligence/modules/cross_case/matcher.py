"""Deterministic cross-case candidate correlation matcher with PII masking and conflict detection."""

from __future__ import annotations

import re

from document_intelligence.domain.enums import (
    CrossCaseReviewDecision,
    ResolvedEntityType,
)
from document_intelligence.domain.models.cross_case import (
    CrossCaseCandidateMatch,
    CrossCaseMatchEvidence,
)
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.modules.entity_resolution.engine.similarity import (
    calculate_string_similarity,
    calculate_token_set_similarity,
    compute_composite_name_similarity,
)

# Common/generic business name components that must not be treated as proof of relation
GENERIC_BUSINESS_TERMS: set[str] = {
    "llc",
    "inc",
    "corp",
    "corporation",
    "ltd",
    "limited",
    "services",
    "solutions",
    "enterprises",
    "consulting",
    "trading",
    "holdings",
    "management",
    "international",
    "global",
    "group",
    "general",
    "technologies",
    "supplies",
    "company",
    "co",
}


def mask_sensitive_value(value: str, entity_type: ResolvedEntityType | str) -> str:
    """Mask sensitive PII fields (account numbers, tax IDs, emails, phones) for safe display."""
    if not value:
        return ""

    val = value.strip()
    type_str = entity_type.value if hasattr(entity_type, "value") else str(entity_type)

    if type_str == ResolvedEntityType.BANK_ACCOUNT_REFERENCE.value or "account" in type_str.lower():
        digits = re.findall(r"\d", val)
        if len(digits) >= 4:
            return f"Account ****{''.join(digits[-4:])}"
        return "****"

    if type_str == ResolvedEntityType.TAX_IDENTIFIER.value or "tax" in type_str.lower():
        if len(val) >= 6:
            return f"***-**-{val[-4:]}"
        return "****"

    # Email masking: j***@domain.com
    if "@" in val:
        parts = val.split("@", 1)
        name, domain = parts[0], parts[1]
        masked_name = name[0] + "***" if name else "***"
        return f"{masked_name}@{domain}"

    # Phone masking
    phone_digits = re.findall(r"\d", val)
    if len(phone_digits) >= 10:
        return f"Phone ****{''.join(phone_digits[-4:])}"

    # General digit sequences exceeding 8 digits
    return re.sub(r"\b\d{8,}\b", lambda m: f"****{m.group(0)[-4:]}", val)


def is_masked_or_incomplete(value: str) -> bool:
    """Check if value is already masked, redacted, or incomplete."""
    if not value or len(value.strip()) <= 3:
        return True
    val = value.strip().lower()
    if "*" in val or "x" * 4 in val or "#" * 4 in val or "unknown" in val or "n/a" in val:
        return True
    return False


def is_overly_generic(name: str) -> bool:
    """Detect if name consists predominantly of generic corporate stop terms."""
    tokens = re.findall(r"\w+", name.lower())
    if not tokens:
        return True
    meaningful = [t for t in tokens if t not in GENERIC_BUSINESS_TERMS and len(t) > 2]
    return len(meaningful) == 0


class CrossCaseMatcher:
    """Evaluates pairs of entity mentions across different cases with conservative matching rules."""

    def __init__(
        self,
        strong_similarity_threshold: float = 0.85,
        weak_similarity_threshold: float = 0.60,
    ) -> None:
        self.strong_threshold = strong_similarity_threshold
        self.weak_threshold = weak_similarity_threshold

    def compare(
        self,
        m1: EntityMention,
        m2: EntityMention,
        scope_id: str,
        organization_id: str,
    ) -> CrossCaseCandidateMatch | None:
        """Compare two entity mentions from different cases and return candidate match if relevant."""
        # 1. Strictly compare distinct cases only
        if m1.case_id == m2.case_id:
            return None

        # 2. Only compare compatible entity types
        if m1.entity_type != m2.entity_type:
            return None

        etype = m1.entity_type
        if etype == ResolvedEntityType.TAX_IDENTIFIER:
            return self._match_tax_identifiers(m1, m2, scope_id, organization_id)
        elif etype in (
            ResolvedEntityType.INVOICE_REFERENCE,
            ResolvedEntityType.TRANSACTION_REFERENCE,
        ):
            return self._match_document_references(m1, m2, scope_id, organization_id)
        elif etype == ResolvedEntityType.BANK_ACCOUNT_REFERENCE:
            return self._match_bank_accounts(m1, m2, scope_id, organization_id)
        elif etype == ResolvedEntityType.ORGANIZATION:
            return self._match_organizations(m1, m2, scope_id, organization_id)
        elif etype == ResolvedEntityType.PERSON:
            return self._match_persons(m1, m2, scope_id, organization_id)

        return None

    def _match_tax_identifiers(
        self, m1: EntityMention, m2: EntityMention, scope_id: str, org_id: str
    ) -> CrossCaseCandidateMatch | None:
        v1 = m1.normalized_value or m1.original_value
        v2 = m2.normalized_value or m2.original_value

        is_m1_masked = is_masked_or_incomplete(v1)
        is_m2_masked = is_masked_or_incomplete(v2)

        if is_m1_masked or is_m2_masked:
            # Masked identifiers cannot be exact matches
            return CrossCaseCandidateMatch(
                scope_id=scope_id,
                organization_id=org_id,
                entity_type=m1.entity_type,
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_value_display=mask_sensitive_value(v1, m1.entity_type),
                candidate_value_display=mask_sensitive_value(v2, m2.entity_type),
                raw_target_value_masked=mask_sensitive_value(m1.original_value, m1.entity_type),
                raw_candidate_value_masked=mask_sensitive_value(m2.original_value, m2.entity_type),
                matching_method="masked_tax_id_heuristic",
                match_classification="WEAK_INDICATOR",
                match_score=0.40,
                decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
                evidence=CrossCaseMatchEvidence(
                    target_case_id=m1.case_id,
                    candidate_case_id=m2.case_id,
                    target_mention_id=m1.mention_id,
                    candidate_mention_id=m2.mention_id,
                    target_document_id=m1.document_id,
                    candidate_document_id=m2.document_id,
                    target_page_number=m1.page_number,
                    candidate_page_number=m2.page_number,
                    target_field_key=m1.field_key,
                    candidate_field_key=m2.field_key,
                    matching_signals=["Masked or partial tax identifier overlap observed"],
                    contradicting_signals=["Identifier is incomplete or partially redacted"],
                    confidence_score=0.40,
                    matching_method="masked_tax_id_heuristic",
                    match_classification="WEAK_INDICATOR",
                ),
            )

        if v1.strip().upper() == v2.strip().upper():
            return CrossCaseCandidateMatch(
                scope_id=scope_id,
                organization_id=org_id,
                entity_type=m1.entity_type,
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_value_display=mask_sensitive_value(v1, m1.entity_type),
                candidate_value_display=mask_sensitive_value(v2, m2.entity_type),
                raw_target_value_masked=mask_sensitive_value(m1.original_value, m1.entity_type),
                raw_candidate_value_masked=mask_sensitive_value(m2.original_value, m2.entity_type),
                matching_method="exact_tax_id_match",
                match_classification="EXACT_IDENTIFIER",
                match_score=0.98,
                decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
                evidence=CrossCaseMatchEvidence(
                    target_case_id=m1.case_id,
                    candidate_case_id=m2.case_id,
                    target_mention_id=m1.mention_id,
                    candidate_mention_id=m2.mention_id,
                    target_document_id=m1.document_id,
                    candidate_document_id=m2.document_id,
                    target_page_number=m1.page_number,
                    candidate_page_number=m2.page_number,
                    target_field_key=m1.field_key,
                    candidate_field_key=m2.field_key,
                    matching_signals=[f"Identical canonical tax identifier: {v1.strip().upper()}"],
                    contradicting_signals=[],
                    confidence_score=0.98,
                    matching_method="exact_tax_id_match",
                    match_classification="EXACT_IDENTIFIER",
                ),
            )

        return None

    def _match_document_references(
        self, m1: EntityMention, m2: EntityMention, scope_id: str, org_id: str
    ) -> CrossCaseCandidateMatch | None:
        v1 = (m1.normalized_value or m1.original_value).strip().upper()
        v2 = (m2.normalized_value or m2.original_value).strip().upper()

        if is_masked_or_incomplete(v1) or is_masked_or_incomplete(v2):
            return None

        # Exact document/invoice/PO reference cross-case
        if v1 == v2:
            return CrossCaseCandidateMatch(
                scope_id=scope_id,
                organization_id=org_id,
                entity_type=m1.entity_type,
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_value_display=v1,
                candidate_value_display=v2,
                raw_target_value_masked=m1.original_value,
                raw_candidate_value_masked=m2.original_value,
                matching_method="exact_reference_match",
                match_classification="EXACT_IDENTIFIER",
                match_score=0.95,
                decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
                evidence=CrossCaseMatchEvidence(
                    target_case_id=m1.case_id,
                    candidate_case_id=m2.case_id,
                    target_mention_id=m1.mention_id,
                    candidate_mention_id=m2.mention_id,
                    target_document_id=m1.document_id,
                    candidate_document_id=m2.document_id,
                    target_page_number=m1.page_number,
                    candidate_page_number=m2.page_number,
                    target_field_key=m1.field_key,
                    candidate_field_key=m2.field_key,
                    matching_signals=[f"Matching reference identifier across cases: {v1}"],
                    contradicting_signals=[],
                    confidence_score=0.95,
                    matching_method="exact_reference_match",
                    match_classification="EXACT_IDENTIFIER",
                ),
            )
        return None

    def _match_bank_accounts(
        self, m1: EntityMention, m2: EntityMention, scope_id: str, org_id: str
    ) -> CrossCaseCandidateMatch | None:
        v1 = re.sub(r"\D", "", m1.normalized_value or m1.original_value)
        v2 = re.sub(r"\D", "", m2.normalized_value or m2.original_value)

        if len(v1) < 6 or len(v2) < 6:
            return None

        if v1 == v2:
            score = 0.96
            classification = "EXACT_IDENTIFIER"
            signals = ["Identical bank account digits detected across cases"]
        elif v1[-4:] == v2[-4:]:
            score = 0.45
            classification = "WEAK_INDICATOR"
            signals = ["Matching last 4 digits only (unverified full account)"]
        else:
            return None

        return CrossCaseCandidateMatch(
            scope_id=scope_id,
            organization_id=org_id,
            entity_type=m1.entity_type,
            target_case_id=m1.case_id,
            candidate_case_id=m2.case_id,
            target_value_display=mask_sensitive_value(m1.original_value, m1.entity_type),
            candidate_value_display=mask_sensitive_value(m2.original_value, m2.entity_type),
            raw_target_value_masked=mask_sensitive_value(m1.original_value, m1.entity_type),
            raw_candidate_value_masked=mask_sensitive_value(m2.original_value, m2.entity_type),
            matching_method="bank_account_digits",
            match_classification=classification,
            match_score=score,
            decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
            evidence=CrossCaseMatchEvidence(
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_document_id=m1.document_id,
                candidate_document_id=m2.document_id,
                target_page_number=m1.page_number,
                candidate_page_number=m2.page_number,
                target_field_key=m1.field_key,
                candidate_field_key=m2.field_key,
                matching_signals=signals,
                contradicting_signals=[],
                confidence_score=score,
                matching_method="bank_account_digits",
                match_classification=classification,
            ),
        )

    def _match_organizations(
        self, m1: EntityMention, m2: EntityMention, scope_id: str, org_id: str
    ) -> CrossCaseCandidateMatch | None:
        name1 = m1.base_name or m1.normalized_value or m1.original_value
        name2 = m2.base_name or m2.normalized_value or m2.original_value

        if not name1 or not name2 or len(name1.strip()) < 3 or len(name2.strip()) < 3:
            return None

        # Check for overly generic business names
        if is_overly_generic(name1) or is_overly_generic(name2):
            return None

        char_sim = calculate_string_similarity(name1, name2)
        tok_sim = calculate_token_set_similarity(name1, name2)
        similarity = compute_composite_name_similarity(name1, name2)
        effective_sim = max(similarity, char_sim) if tok_sim >= 0.4 else similarity

        if effective_sim < self.weak_threshold:
            return None

        matching_signals: list[str] = []
        contradicting_signals: list[str] = []

        # Check for conflicting tax IDs if available in mention metadata
        tax1 = m1.metadata.get("tax_id")
        tax2 = m2.metadata.get("tax_id")
        if tax1 and tax2 and tax1.strip().upper() != tax2.strip().upper():
            contradicting_signals.append(
                f"Conflicting tax IDs: '{mask_sensitive_value(tax1, 'TAX_IDENTIFIER')}' != '{mask_sensitive_value(tax2, 'TAX_IDENTIFIER')}'"
            )

        # Check jurisdictions if available
        if m1.jurisdiction and m2.jurisdiction and m1.jurisdiction != m2.jurisdiction:
            contradicting_signals.append(
                f"Different jurisdictions: '{m1.jurisdiction}' vs '{m2.jurisdiction}'"
            )

        if effective_sim >= 0.98:
            matching_signals.append(f"High-confidence organization name match: '{name1}'")
            classification = "HIGH_CONFIDENCE_FUZZY"
            base_score = 0.92
        elif effective_sim >= self.strong_threshold:
            matching_signals.append(f"Fuzzy organization name similarity ({effective_sim:.2f})")
            classification = "HIGH_CONFIDENCE_FUZZY"
            base_score = round(effective_sim * 0.90, 2)
        else:
            matching_signals.append(f"Partial name similarity ({effective_sim:.2f})")
            classification = "WEAK_INDICATOR"
            base_score = round(effective_sim * 0.75, 2)

        # Penalize if contradicting signals exist
        if contradicting_signals:
            classification = "CONFLICTING"
            base_score = max(0.20, round(base_score * 0.40, 2))

        return CrossCaseCandidateMatch(
            scope_id=scope_id,
            organization_id=org_id,
            entity_type=m1.entity_type,
            target_case_id=m1.case_id,
            candidate_case_id=m2.case_id,
            target_value_display=name1,
            candidate_value_display=name2,
            raw_target_value_masked=m1.original_value,
            raw_candidate_value_masked=m2.original_value,
            matching_method="composite_name_similarity",
            match_classification=classification,
            match_score=base_score,
            decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
            evidence=CrossCaseMatchEvidence(
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_document_id=m1.document_id,
                candidate_document_id=m2.document_id,
                target_page_number=m1.page_number,
                candidate_page_number=m2.page_number,
                target_field_key=m1.field_key,
                candidate_field_key=m2.field_key,
                matching_signals=matching_signals,
                contradicting_signals=contradicting_signals,
                confidence_score=base_score,
                matching_method="composite_name_similarity",
                match_classification=classification,
            ),
        )

    def _match_persons(
        self, m1: EntityMention, m2: EntityMention, scope_id: str, org_id: str
    ) -> CrossCaseCandidateMatch | None:
        name1 = m1.normalized_value or m1.original_value
        name2 = m2.normalized_value or m2.original_value

        if not name1 or not name2 or len(name1.strip()) < 3 or len(name2.strip()) < 3:
            return None

        similarity = compute_composite_name_similarity(name1, name2)
        if similarity < self.strong_threshold:
            return None

        matching_signals = [f"Person name similarity ({similarity:.2f}) across cases"]
        contradicting_signals: list[str] = []

        classification = "STRONG_SIMILARITY" if similarity >= 0.95 else "WEAK_INDICATOR"
        score = round(similarity * 0.88, 2)

        return CrossCaseCandidateMatch(
            scope_id=scope_id,
            organization_id=org_id,
            entity_type=m1.entity_type,
            target_case_id=m1.case_id,
            candidate_case_id=m2.case_id,
            target_value_display=name1,
            candidate_value_display=name2,
            raw_target_value_masked=m1.original_value,
            raw_candidate_value_masked=m2.original_value,
            matching_method="composite_person_name_similarity",
            match_classification=classification,
            match_score=score,
            decision_status=CrossCaseReviewDecision.PENDING_REVIEW,
            evidence=CrossCaseMatchEvidence(
                target_case_id=m1.case_id,
                candidate_case_id=m2.case_id,
                target_mention_id=m1.mention_id,
                candidate_mention_id=m2.mention_id,
                target_document_id=m1.document_id,
                candidate_document_id=m2.document_id,
                target_page_number=m1.page_number,
                candidate_page_number=m2.page_number,
                target_field_key=m1.field_key,
                candidate_field_key=m2.field_key,
                matching_signals=matching_signals,
                contradicting_signals=contradicting_signals,
                confidence_score=score,
                matching_method="composite_person_name_similarity",
                match_classification=classification,
            ),
        )
