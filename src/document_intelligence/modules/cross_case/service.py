"""Application service orchestrating cross-case investigation scopes, correlation, and reviews."""

from __future__ import annotations

import logging
from typing import Any

from document_intelligence.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from document_intelligence.domain.enums import (
    AuditEventType,
    CaseStatus,
    CrossCaseReviewDecision,
    EntityType,
    GraphEdgePredicate,
    GraphNodeType,
    ResolvedEntityType,
)
from document_intelligence.domain.identifiers import generate_id, utc_now
from document_intelligence.domain.models.auth import CaseRole, SystemRole
from document_intelligence.domain.models.cross_case import (
    CrossCaseCandidateMatch,
    CrossCaseCorrelationResult,
    CrossCaseMatchEvidence,
    CrossCaseMatchReview,
    CrossCaseScope,
)
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.domain.models.graph import (
    GraphEdge,
    GraphNode,
    GraphSnapshot,
    deterministic_edge_id,
    deterministic_node_id,
)
from document_intelligence.infrastructure.persistence.models import (
    CrossCaseCandidateMatchModel,
    CrossCaseCandidateReviewModel,
    CrossCaseScopeModel,
    UserModel,
)
from document_intelligence.infrastructure.repositories.case_repository import CaseRepository
from document_intelligence.infrastructure.repositories.cross_case_repository import (
    CrossCaseRepository,
)
from document_intelligence.infrastructure.repositories.document_repository import (
    DocumentRepository,
)
from document_intelligence.infrastructure.repositories.evidence_repository import (
    EvidenceRepository,
)
from document_intelligence.infrastructure.repositories.finding_repository import (
    FindingRepository,
)
from document_intelligence.modules.audit.ledger import AuditLedgerService
from document_intelligence.modules.auth.service import CaseAccessService
from document_intelligence.modules.cases.service import CaseService
from document_intelligence.modules.cross_case.engine import CrossCaseCorrelationEngine
from document_intelligence.modules.entity_resolution.service import EntityResolutionService
from document_intelligence.modules.graph.projector import EvidenceGraphProjector

logger = logging.getLogger(__name__)

MAX_SCOPE_CASES = 20


class CrossCaseCorrelationService:
    """Coordinates cross-case scoping, deterministic correlation inference, and investigator reviews."""

    def __init__(
        self,
        cross_case_repo: CrossCaseRepository,
        case_access_service: CaseAccessService,
        case_service: CaseService,
        case_repo: CaseRepository,
        document_repo: DocumentRepository,
        evidence_repo: EvidenceRepository,
        finding_repo: FindingRepository,
        audit_service: AuditLedgerService,
        entity_resolution_service: EntityResolutionService,
        engine: CrossCaseCorrelationEngine | None = None,
        graph_projector: EvidenceGraphProjector | None = None,
    ) -> None:
        self.repo = cross_case_repo
        self.case_access = case_access_service
        self.case_service = case_service
        self.case_repo = case_repo
        self.document_repo = document_repo
        self.evidence_repo = evidence_repo
        self.finding_repo = finding_repo
        self.audit_service = audit_service
        self.entity_resolution_service = entity_resolution_service
        self.engine = engine or CrossCaseCorrelationEngine()
        self.graph_projector = graph_projector or EvidenceGraphProjector()

    def _get_user_org_id(self, user: UserModel) -> str:
        """Determine primary organization ID for the user principal."""
        org_id = getattr(user, "organization_id", None)
        if isinstance(org_id, str) and org_id:
            return org_id
        # Fallback query user's organization memberships
        from sqlalchemy import select

        from document_intelligence.infrastructure.persistence.models import (
            OrganizationMembershipModel,
        )

        stmt = select(OrganizationMembershipModel).where(
            OrganizationMembershipModel.user_id == user.id
        )
        membership = self.case_access.repo.db.scalars(stmt).first()
        if membership and isinstance(membership.organization_id, str):
            return str(membership.organization_id)
        # Or default org
        default_org = self.case_access.repo.get_or_create_default_org()
        return str(default_org.id)

    def validate_scope_cases(
        self, user: UserModel, case_ids: list[str], min_role: CaseRole = CaseRole.VIEWER
    ) -> str:
        """Verify that user has valid access to every case in the scope; returns organization ID."""
        if not case_ids:
            raise ValidationException(
                "Cross-case investigation scope must include at least one case."
            )

        if len(case_ids) > MAX_SCOPE_CASES:
            raise ValidationException(
                f"Scope exceeds maximum limit of {MAX_SCOPE_CASES} cases (requested {len(case_ids)})."
            )

        org_id = self._get_user_org_id(user)

        # Revalidate access for each requested case
        for cid in case_ids:
            case = self.case_access.repo.get_case(cid)
            if not case:
                # Anti-enumeration: uniform 404
                raise NotFoundException(f"Case '{cid}' not found or inaccessible.")

            # Tenant boundary check: case must belong to user's organization if assigned
            if case.organization_id and case.organization_id != org_id:
                if user.system_role != SystemRole.SYSTEM_ADMIN.value:
                    raise NotFoundException(f"Case '{cid}' not found or inaccessible.")

            # Reject archived cases
            if case.status == CaseStatus.ARCHIVED.value:
                raise ValidationException(
                    f"Cannot include archived case '{cid}' in active correlation scope."
                )

            # Case-level RBAC check
            try:
                self.case_access.check_case_access(user=user, case_id=cid, min_role=min_role)
            except (NotFoundException, ForbiddenException):
                raise NotFoundException(f"Case '{cid}' not found or inaccessible.") from None

        return org_id

    @staticmethod
    def _parse_case_ids(raw_case_ids: Any) -> list[str]:
        if isinstance(raw_case_ids, str):
            import json

            try:
                raw_case_ids = json.loads(raw_case_ids)
            except Exception:
                return []
        return list(raw_case_ids or [])

    # -------------------------------------------------------------------------
    # Scope Lifecycle
    # -------------------------------------------------------------------------

    def create_scope(
        self,
        name: str,
        case_ids: list[str],
        user: UserModel,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CrossCaseScope:
        """Create a new explicit cross-case investigation scope."""
        org_id = self.validate_scope_cases(user, case_ids, min_role=CaseRole.VIEWER)

        scope_id = generate_id()
        now = utc_now()
        model = CrossCaseScopeModel(
            id=scope_id,
            organization_id=org_id,
            name=name.strip(),
            description=description.strip() if description else None,
            case_ids=list(dict.fromkeys(case_ids)),  # Deduplicate preserving order
            created_by=user.id,
            created_at=now,
            updated_at=now,
            is_active=True,
            scope_metadata=metadata or {},
        )
        self.repo.create_scope(model)

        # Record audit event on the primary/first case in the scope
        primary_case_id = case_ids[0]
        try:
            self.audit_service.record_event(
                case_id=primary_case_id,
                event_type=AuditEventType.CROSS_CASE_SCOPE_CREATED,
                entity_type=EntityType.CASE,
                entity_id=scope_id,
                actor_id=user.id,
                payload={
                    "scope_id": scope_id,
                    "scope_name": name,
                    "organization_id": org_id,
                    "case_count": len(case_ids),
                    "case_ids": case_ids,
                },
            )
        except Exception as e:
            logger.warning("Audit logging failed during scope creation: %s", e)

        return self._to_domain_scope(model)

    def get_scope(self, scope_id: str, user: UserModel) -> CrossCaseScope:
        """Retrieve scope details after revalidating current case authorizations."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        # Revalidate access to every case currently in the scope
        case_ids = self._parse_case_ids(model.case_ids)
        self.validate_scope_cases(user, case_ids, min_role=CaseRole.VIEWER)
        return self._to_domain_scope(model)

    def list_scopes(self, user: UserModel) -> list[CrossCaseScope]:
        """List active scopes for the user's organization."""
        org_id = self._get_user_org_id(user)
        models = self.repo.list_scopes(organization_id=org_id, is_active=True)

        accessible: list[CrossCaseScope] = []
        for m in models:
            # Check user access to cases in scope
            try:
                case_ids = self._parse_case_ids(m.case_ids)
                self.validate_scope_cases(user, case_ids, min_role=CaseRole.VIEWER)
                accessible.append(self._to_domain_scope(m))
            except NotFoundException:
                continue
        return accessible

    def update_scope_cases(
        self, scope_id: str, case_ids: list[str], user: UserModel
    ) -> CrossCaseScope:
        """Update case membership for an investigation scope."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        # Revalidate new cases
        self.validate_scope_cases(user, case_ids, min_role=CaseRole.INVESTIGATOR)

        old_cases = self._parse_case_ids(model.case_ids)
        model.case_ids = list(dict.fromkeys(case_ids))
        self.repo.update_scope(model)

        # Audit modification
        if model.case_ids:
            try:
                self.audit_service.record_event(
                    case_id=model.case_ids[0],
                    event_type=AuditEventType.CROSS_CASE_SCOPE_MODIFIED,
                    entity_type=EntityType.CASE,
                    entity_id=scope_id,
                    actor_id=user.id,
                    payload={
                        "scope_id": scope_id,
                        "old_case_ids": old_cases,
                        "new_case_ids": model.case_ids,
                    },
                )
            except Exception as e:
                logger.warning("Audit logging failed during scope update: %s", e)

        return self._to_domain_scope(model)

    # -------------------------------------------------------------------------
    # Correlation Execution
    # -------------------------------------------------------------------------

    def run_correlation(self, scope_id: str, user: UserModel) -> CrossCaseCorrelationResult:
        """Execute deterministic cross-case correlation across all cases in the scope."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        # Revalidate user access at runtime
        case_ids = self._parse_case_ids(model.case_ids)
        org_id = self.validate_scope_cases(user, case_ids, min_role=CaseRole.INVESTIGATOR)

        # 1. Harvest entity mentions across all cases in scope
        all_mentions: list[EntityMention] = []
        for cid in case_ids:
            try:
                mentions = self.entity_resolution_service.harvest_mentions_from_extractions(cid)
                all_mentions.extend(mentions)
            except Exception as e:
                logger.debug("Mentions harvest skipped for case %s: %s", cid, e)

        # 2. Correlate across cases using deterministic rules
        result = self.engine.correlate(
            scope_id=scope_id,
            organization_id=org_id,
            mentions=all_mentions,
            case_ids=case_ids,
        )

        # 3. Clear previous pending candidate matches and persist newly evaluated ones
        self.repo.clear_scope_matches(scope_id)
        match_models = [self._to_match_model(m) for m in result.candidate_matches]
        self.repo.save_candidate_matches(match_models)

        # 4. Audit execution
        if case_ids:
            try:
                self.audit_service.record_event(
                    case_id=case_ids[0],
                    event_type=AuditEventType.CROSS_CASE_CORRELATION_EXECUTED,
                    entity_type=EntityType.CASE,
                    entity_id=scope_id,
                    actor_id=user.id,
                    payload={
                        "scope_id": scope_id,
                        "cases_analyzed": case_ids,
                        "total_mentions_compared": result.total_mentions_compared,
                        "candidate_matches_count": len(result.candidate_matches),
                        "duration_ms": result.execution_duration_ms,
                    },
                )
            except Exception as e:
                logger.warning("Audit logging failed during correlation execution: %s", e)

        return result

    # -------------------------------------------------------------------------
    # Candidate Matches & Reviews
    # -------------------------------------------------------------------------

    def list_candidates(
        self,
        scope_id: str,
        user: UserModel,
        decision_status: str | None = None,
        entity_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[CrossCaseCandidateMatch], int]:
        """List paginated correlation candidates for a scope."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        case_ids = self._parse_case_ids(model.case_ids)
        self.validate_scope_cases(user, case_ids, min_role=CaseRole.VIEWER)

        match_models, total = self.repo.list_candidate_matches(
            scope_id=scope_id,
            decision_status=decision_status,
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )

        candidates = [self._to_domain_match(m) for m in match_models]
        return candidates, total

    def get_candidate(
        self, scope_id: str, match_id: str, user: UserModel
    ) -> CrossCaseCandidateMatch:
        """Retrieve candidate match details."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        self.validate_scope_cases(user, model.case_ids, min_role=CaseRole.VIEWER)

        match = self.repo.get_candidate_match(match_id)
        if not match or match.scope_id != scope_id:
            raise NotFoundException(f"Candidate match '{match_id}' not found in scope.")

        return self._to_domain_match(match)

    def review_candidate(
        self,
        scope_id: str,
        match_id: str,
        decision: CrossCaseReviewDecision,
        rationale: str,
        user: UserModel,
    ) -> CrossCaseCandidateMatch:
        """Record an investigator review decision on a correlation candidate."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        # Enforce role: Reviewer or Admin required for formal candidate disposition
        case_ids = self._parse_case_ids(model.case_ids)
        self.validate_scope_cases(user, case_ids, min_role=CaseRole.REVIEWER)

        match = self.repo.get_candidate_match(match_id)
        if not match or match.scope_id != scope_id:
            raise NotFoundException(f"Candidate match '{match_id}' not found in scope.")

        prev_status = match.decision_status
        new_status = decision.value

        # Persist review record
        rev_id = generate_id()
        review_model = CrossCaseCandidateReviewModel(
            id=rev_id,
            match_id=match_id,
            scope_id=scope_id,
            decision=new_status,
            reviewer_id=user.id,
            reviewer_username=user.username,
            rationale=rationale.strip(),
            previous_status=prev_status,
            new_status=new_status,
            reviewed_at=utc_now(),
        )
        self.repo.save_review(review_model)

        # Update candidate status
        updated_match = self.repo.update_match_status(match, new_status)

        # Audit review
        if case_ids:
            try:
                self.audit_service.record_event(
                    case_id=case_ids[0],
                    event_type=AuditEventType.CROSS_CASE_CANDIDATE_REVIEWED,
                    entity_type=EntityType.REVIEW_DECISION,
                    entity_id=match_id,
                    actor_id=user.id,
                    payload={
                        "scope_id": scope_id,
                        "match_id": match_id,
                        "decision": new_status,
                        "rationale": rationale,
                    },
                )
            except Exception as e:
                logger.warning("Audit logging failed during candidate review: %s", e)

        return self._to_domain_match(updated_match)

    # -------------------------------------------------------------------------
    # Cross-Case Evidence Graph
    # -------------------------------------------------------------------------

    def get_cross_case_graph(
        self, scope_id: str, user: UserModel, max_hops: int = 2, max_nodes: int = 500
    ) -> GraphSnapshot:
        """Project multi-case Evidence Graph with cross-case correlation candidate overlays."""
        model = self.repo.get_scope(scope_id)
        if not model or not model.is_active:
            raise NotFoundException(f"Investigation scope '{scope_id}' not found.")

        case_ids = self._parse_case_ids(model.case_ids)
        self.validate_scope_cases(user, case_ids, min_role=CaseRole.VIEWER)

        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        # 1. Project individual case graphs
        for cid in case_ids:
            case = self.case_repo.get_by_id(cid)
            if not case:
                continue
            docs, _ = self.document_repo.list_by_case(cid)
            evs, _ = self.evidence_repo.list_by_case(cid)
            findings, _ = self.finding_repo.list_by_case(cid)

            case_data = self.graph_projector.project_case(
                case=case,
                documents=docs,
                evidence_nodes=evs,
                forensic_findings=findings,
                consistency_findings=[],
                detected_relationships=[],
                entity_matches=[],
            )

            for n_id, node in case_data.nodes.items():
                if len(nodes) < max_nodes:
                    nodes[n_id] = node
            for e_id, edge in case_data.edges.items():
                if len(edges) < max_nodes * 2:
                    edges[e_id] = edge

        # 2. Overlay cross-case correlation candidate edges
        matches, _ = self.repo.list_candidate_matches(scope_id=scope_id, limit=200)
        for m in matches:
            # Only connect if both endpoint cases are represented
            src_node_id = deterministic_node_id(
                m.target_case_id, GraphNodeType.ORGANIZATION, m.target_value_display
            )
            tgt_node_id = deterministic_node_id(
                m.candidate_case_id, GraphNodeType.ORGANIZATION, m.candidate_value_display
            )

            # Ensure endpoints exist as virtual graph nodes if not already projected
            if src_node_id not in nodes and len(nodes) < max_nodes:
                nodes[src_node_id] = GraphNode(
                    id=src_node_id,
                    case_id=m.target_case_id,
                    node_type=GraphNodeType.ORGANIZATION,
                    source_entity_type="CrossCaseEntity",
                    source_entity_id=m.target_case_id,
                    label=m.target_value_display,
                    display_attributes={
                        "classification": m.match_classification,
                        "scope_id": scope_id,
                    },
                    provenance={"case_id": m.target_case_id},
                )
            if tgt_node_id not in nodes and len(nodes) < max_nodes:
                nodes[tgt_node_id] = GraphNode(
                    id=tgt_node_id,
                    case_id=m.candidate_case_id,
                    node_type=GraphNodeType.ORGANIZATION,
                    source_entity_type="CrossCaseEntity",
                    source_entity_id=m.candidate_case_id,
                    label=m.candidate_value_display,
                    display_attributes={
                        "classification": m.match_classification,
                        "scope_id": scope_id,
                    },
                    provenance={"case_id": m.candidate_case_id},
                )

            # Create cross-case edge
            edge_id = deterministic_edge_id(
                case_id=scope_id,
                source_node_id=src_node_id,
                predicate=GraphEdgePredicate.CORRELATES_WITH,
                target_node_id=tgt_node_id,
                source_rel_id=m.id,
            )
            edges[edge_id] = GraphEdge(
                id=edge_id,
                case_id=scope_id,
                source_node_id=src_node_id,
                target_node_id=tgt_node_id,
                predicate=GraphEdgePredicate.CORRELATES_WITH.value,
                status="CONFIRMED" if m.decision_status == "ACCEPTED" else "CANDIDATE",
                status_determination_method="CROSS_CASE_CORRELATION",
                score=m.match_score,
                explanation=f"Cross-case correlation ({m.match_classification}): {m.target_value_display} ~ {m.candidate_value_display}",
                metadata={
                    "scope_id": scope_id,
                    "target_case_id": m.target_case_id,
                    "candidate_case_id": m.candidate_case_id,
                    "match_id": m.id,
                },
            )

        return GraphSnapshot(
            case_id=scope_id,
            nodes=list(nodes.values()),
            edges=list(edges.values()),
            total_nodes=len(nodes),
            total_edges=len(edges),
            truncated=len(nodes) >= max_nodes,
            query_metadata={"scope_id": scope_id, "cases": model.case_ids},
        )

    # -------------------------------------------------------------------------
    # Helper Mappers
    # -------------------------------------------------------------------------

    def _to_domain_scope(self, model: CrossCaseScopeModel) -> CrossCaseScope:
        case_ids = model.case_ids
        if isinstance(case_ids, str):
            import json

            case_ids = json.loads(case_ids)
        metadata = model.scope_metadata or {}
        if isinstance(metadata, str):
            import json

            metadata = json.loads(metadata)
        return CrossCaseScope(
            id=model.id,
            organization_id=model.organization_id,
            name=model.name,
            description=model.description,
            case_ids=case_ids,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            is_active=model.is_active,
            metadata=metadata,
        )

    def _to_match_model(self, m: CrossCaseCandidateMatch) -> CrossCaseCandidateMatchModel:
        return CrossCaseCandidateMatchModel(
            id=m.id,
            scope_id=m.scope_id,
            organization_id=m.organization_id,
            entity_type=m.entity_type.value,
            target_case_id=m.target_case_id,
            candidate_case_id=m.candidate_case_id,
            target_value_display=m.target_value_display,
            candidate_value_display=m.candidate_value_display,
            raw_target_value_masked=m.raw_target_value_masked,
            raw_candidate_value_masked=m.raw_candidate_value_masked,
            matching_method=m.matching_method,
            match_classification=m.match_classification,
            match_score=m.match_score,
            decision_status=m.decision_status.value,
            evidence_payload=m.evidence.model_dump(),
            created_at=m.created_at,
        )

    def _to_domain_match(self, model: CrossCaseCandidateMatchModel) -> CrossCaseCandidateMatch:
        reviews = self.repo.list_reviews_for_match(model.id)
        review_domain = [
            CrossCaseMatchReview(
                id=r.id,
                match_id=r.match_id,
                scope_id=r.scope_id,
                decision=CrossCaseReviewDecision(r.decision),
                reviewer_id=r.reviewer_id,
                reviewer_username=r.reviewer_username,
                rationale=r.rationale,
                previous_status=r.previous_status,
                new_status=r.new_status,
                reviewed_at=r.reviewed_at,
            )
            for r in reviews
        ]

        payload = model.evidence_payload
        if isinstance(payload, str):
            import json

            payload = json.loads(payload)
        evidence = CrossCaseMatchEvidence.model_validate(payload)

        return CrossCaseCandidateMatch(
            id=model.id,
            scope_id=model.scope_id,
            organization_id=model.organization_id,
            entity_type=ResolvedEntityType(model.entity_type),
            target_case_id=model.target_case_id,
            candidate_case_id=model.candidate_case_id,
            target_value_display=model.target_value_display,
            candidate_value_display=model.candidate_value_display,
            raw_target_value_masked=model.raw_target_value_masked,
            raw_candidate_value_masked=model.raw_candidate_value_masked,
            matching_method=model.matching_method,
            match_classification=model.match_classification,
            match_score=model.match_score,
            decision_status=CrossCaseReviewDecision(model.decision_status),
            evidence=evidence,
            review_history=review_domain,
            created_at=model.created_at,
        )
