"""Unit tests for deterministic entity matching, contradiction detection, and clustering."""

from __future__ import annotations

from decimal import Decimal

import pytest

from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    EntityMatchClassification,
    EntityMatchingMethod,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.modules.entity_resolution.engine.matcher import (
    DeterministicEntityMatcher,
)
from document_intelligence.modules.entity_resolution.engine.resolver import (
    EntityResolutionEngine,
)


def _build_mention(
    mention_id: str,
    doc_id: str,
    entity_type: ResolvedEntityType,
    norm_val: str,
    case_id: str = "case-01",
    base_name: str | None = None,
    legal_suffix: str | None = None,
    numeric_amount: Decimal | None = None,
    currency_code: str | None = None,
    jurisdiction: str | None = None,
    id_type: str | None = None,
    metadata: dict | None = None,
) -> EntityMention:
    return EntityMention(
        mention_id=mention_id,
        case_id=case_id,
        document_id=doc_id,
        page_number=1,
        processing_run_id="run-ext-01",
        field_key="test_field",
        entity_type=entity_type,
        original_value=norm_val,
        normalized_value=norm_val,
        base_name=base_name,
        legal_suffix=legal_suffix,
        numeric_amount=numeric_amount,
        currency_code=currency_code,
        jurisdiction=jurisdiction,
        identifier_type=id_type,
        metadata=metadata or {},
    )


class TestDeterministicEntityMatcher:
    """Test pairwise matching rules, conservative scoring, and contradiction detection."""

    def setup_method(self) -> None:
        self.matcher = DeterministicEntityMatcher()

    def test_exact_tax_identifier_match(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.TAX_IDENTIFIER,
            "123456789",
            jurisdiction="US",
            id_type="US_EIN",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.TAX_IDENTIFIER,
            "123456789",
            jurisdiction="US",
            id_type="US_EIN",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.EXACT_MATCH
        assert match.match_score == 1.0
        assert match.matching_method == EntityMatchingMethod.EXACT_IDENTIFIER

    def test_conflicting_tax_identifiers(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.TAX_IDENTIFIER,
            "123456789",
            jurisdiction="US",
            id_type="US_EIN",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.TAX_IDENTIFIER,
            "987654321",
            jurisdiction="US",
            id_type="US_EIN",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY
        assert match.match_score == 0.0
        assert match.decision_status == MatchDecisionStatus.REJECTED

    def test_tax_identifier_type_mismatch_conflicts(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.TAX_IDENTIFIER,
            "123456789",
            jurisdiction="US",
            id_type="US_EIN",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.TAX_IDENTIFIER,
            "123456789",
            jurisdiction="UK",
            id_type="UK_VAT",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY
        assert match.decision_status == MatchDecisionStatus.REJECTED

    def test_exact_invoice_reference_match(self) -> None:
        m1 = _build_mention("m1", "doc1", ResolvedEntityType.INVOICE_REFERENCE, "INV-00123")
        m2 = _build_mention("m2", "doc2", ResolvedEntityType.INVOICE_REFERENCE, "INV-00123")
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.EXACT_MATCH
        assert match.match_score == 1.0

    def test_invoice_reference_leading_zero_variance(self) -> None:
        m1 = _build_mention("m1", "doc1", ResolvedEntityType.INVOICE_REFERENCE, "00123")
        m2 = _build_mention("m2", "doc2", ResolvedEntityType.INVOICE_REFERENCE, "123")
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.STRONG_CANDIDATE
        assert match.match_score == 0.85
        assert len(match.evidence.contradicting_signals) > 0

    def test_masked_bank_account_last4_weak_evidence(self) -> None:
        m1 = _build_mention("m1", "doc1", ResolvedEntityType.BANK_ACCOUNT_REFERENCE, "****1098")
        m2 = _build_mention("m2", "doc2", ResolvedEntityType.BANK_ACCOUNT_REFERENCE, "****1098")
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        # Masked last-4 match must be weak and ambiguous, NEVER auto-confirmed identity
        assert match.match_classification == EntityMatchClassification.WEAK_AMBIGUOUS
        assert match.match_score <= 0.50
        assert match.decision_status == MatchDecisionStatus.AMBIGUOUS
        assert any("collision probability" in s for s in match.evidence.contradicting_signals)

    def test_currency_amount_same_value_different_currencies_conflicts(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.CURRENCY_AMOUNT,
            "USD:1250.00",
            numeric_amount=Decimal("1250.00"),
            currency_code="USD",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.CURRENCY_AMOUNT,
            "EUR:1250.00",
            numeric_amount=Decimal("1250.00"),
            currency_code="EUR",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY
        assert match.decision_status == MatchDecisionStatus.REJECTED

    def test_currency_amount_exact_equality_with_evidentiary_disclaimer(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.CURRENCY_AMOUNT,
            "USD:1250.00",
            numeric_amount=Decimal("1250.00"),
            currency_code="USD",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.CURRENCY_AMOUNT,
            "USD:1250.00",
            numeric_amount=Decimal("1250.00"),
            currency_code="USD",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.NORMALIZED_EXACT_MATCH
        # Explicit reminder that amount coincidence alone does not establish legal identity
        assert any("Amount coincidence alone" in s for s in match.evidence.matching_signals)

    def test_similar_organization_names(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.ORGANIZATION,
            "acme corporation",
            base_name="acme",
            legal_suffix="CORP",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.ORGANIZATION,
            "acme incorporated",
            base_name="acme",
            legal_suffix="INC",
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        # Base names match but legal suffixes differ -> weak/ambiguous, not confirmed
        assert match.match_classification == EntityMatchClassification.WEAK_AMBIGUOUS
        assert match.decision_status == MatchDecisionStatus.AMBIGUOUS

    def test_organization_contradicting_tax_ids_suppress_match(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.ORGANIZATION,
            "acme corp",
            base_name="acme",
            legal_suffix="CORP",
            metadata={"tax_id": "11-1111111"},
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.ORGANIZATION,
            "acme corp",
            base_name="acme",
            legal_suffix="CORP",
            metadata={"tax_id": "22-2222222"},
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY
        assert match.decision_status == MatchDecisionStatus.REJECTED

    def test_composite_match_boosts_confidence(self) -> None:
        # Organization with matching name AND shared invoice reference
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.ORGANIZATION,
            "acme global logistics",
            metadata={"invoice_number": "INV-9900"},
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.ORGANIZATION,
            "acme global logistics",
            metadata={"invoice_number": "INV-9900"},
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.matching_method == EntityMatchingMethod.COMPOSITE_SIGNALS
        assert any("Shared invoice reference" in s for s in match.evidence.matching_signals)

    def test_same_person_name_warning(self) -> None:
        m1 = _build_mention(
            "m1", "doc1", ResolvedEntityType.PERSON, "john smith", base_name="john smith"
        )
        m2 = _build_mention(
            "m2", "doc2", ResolvedEntityType.PERSON, "john smith", base_name="john smith"
        )
        match = self.matcher.compare_mentions(m1, m2, run_id="res-run-01")
        assert match is not None
        assert match.match_classification == EntityMatchClassification.STRONG_CANDIDATE
        # Explicit disclaimer that personal identity requires corroboration
        assert any("Similarity is not identity" in s for s in match.evidence.contradicting_signals)


class TestEntityResolutionEngineClustering:
    """Test blocking, clustering, and cross-case isolation in resolution engine."""

    def setup_method(self) -> None:
        self.engine = EntityResolutionEngine()

    def test_cross_case_mentions_strictly_rejected(self) -> None:
        m1 = _build_mention("m1", "doc1", ResolvedEntityType.ORGANIZATION, "acme", case_id="case-A")
        m2 = _build_mention("m2", "doc2", ResolvedEntityType.ORGANIZATION, "acme", case_id="case-B")
        with pytest.raises(SecurityException, match="Cross-case entity resolution prohibited"):
            self.engine.resolve_entities(case_id="case-A", mentions=[m1, m2], run_id="run-01")

    def test_multi_document_entity_clustering(self) -> None:
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.ORGANIZATION,
            "cyberdyne systems",
            base_name="cyberdyne systems",
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.ORGANIZATION,
            "cyberdyne systems",
            base_name="cyberdyne systems",
        )
        m3 = _build_mention(
            "m3",
            "doc3",
            ResolvedEntityType.ORGANIZATION,
            "cyberdyne systems corp",
            base_name="cyberdyne systems",
            legal_suffix="CORP",
        )
        m4 = _build_mention(
            "m4",
            "doc4",
            ResolvedEntityType.ORGANIZATION,
            "weyland yutani corp",
            base_name="weyland yutani",
            legal_suffix="CORP",
        )

        res = self.engine.resolve_entities("case-01", [m1, m2, m3, m4], run_id="run-01")
        assert res.total_mentions == 4
        assert len(res.resolved_entities) == 1
        cluster = res.resolved_entities[0]
        assert set(cluster.mention_ids) == {"m1", "m2", "m3"}
        assert len(cluster.document_ids) == 3
        # m4 remains unclustered
        assert len(res.unresolved_mentions) == 1
        assert res.unresolved_mentions[0].mention_id == "m4"

    def test_contradiction_prevents_clustering(self) -> None:
        # Two organizations with same name but conflicting tax IDs
        m1 = _build_mention(
            "m1",
            "doc1",
            ResolvedEntityType.ORGANIZATION,
            "apex corp",
            base_name="apex",
            metadata={"tax_id": "TAX-1"},
        )
        m2 = _build_mention(
            "m2",
            "doc2",
            ResolvedEntityType.ORGANIZATION,
            "apex corp",
            base_name="apex",
            metadata={"tax_id": "TAX-2"},
        )

        res = self.engine.resolve_entities("case-01", [m1, m2], run_id="run-01")
        # Contradiction must prevent cluster formation
        assert len(res.resolved_entities) == 0
        assert len(res.unresolved_mentions) == 2
