"""Deterministic cross-document entity resolution coordinator with blocking and bounded execution."""

from __future__ import annotations

import collections
import time
from typing import Any

from document_intelligence.core.exceptions import SecurityException
from document_intelligence.domain.enums import (
    EntityMatchClassification,
    MatchDecisionStatus,
    ResolvedEntityType,
)
from document_intelligence.domain.identifiers import generate_id
from document_intelligence.domain.models.entity_resolution import (
    EntityCandidateMatch,
    EntityMention,
    EntityResolutionResult,
    ResolvedEntity,
)
from document_intelligence.modules.entity_resolution.engine.matcher import (
    DeterministicEntityMatcher,
)


class EntityResolutionEngine:
    """Coordinates deterministic blocking, candidate matching, and entity clustering within a case."""

    def __init__(
        self,
        matcher: DeterministicEntityMatcher | None = None,
        max_comparisons: int = 5000,
        cluster_threshold: float = 0.80,
    ) -> None:
        self.matcher = matcher or DeterministicEntityMatcher()
        self.max_comparisons = max_comparisons
        self.cluster_threshold = cluster_threshold

    def resolve_entities(
        self,
        case_id: str,
        mentions: list[EntityMention],
        run_id: str,
        options: dict[str, Any] | None = None,
    ) -> EntityResolutionResult:
        """Execute deterministic entity resolution across mentions in a single case."""
        start_time = time.perf_counter()

        # 1. Strict cross-case isolation check
        for m in mentions:
            if m.case_id != case_id:
                raise SecurityException(
                    f"Cross-case entity resolution prohibited: mention case '{m.case_id}' != '{case_id}'."
                )

        if not mentions:
            return EntityResolutionResult(
                case_id=case_id,
                processing_run_id=run_id,
                total_mentions=0,
                total_comparisons=0,
                execution_duration_ms=0.0,
            )

        # 2. Deterministic blocking to avoid O(N^2) explosion
        blocks: dict[str, list[EntityMention]] = collections.defaultdict(list)
        for m in mentions:
            key = self._compute_blocking_key(m)
            blocks[key].append(m)

        blocking_summary = {k: len(v) for k, v in blocks.items()}

        candidate_matches: list[EntityCandidateMatch] = []
        compared_pairs: set[tuple[str, str]] = set()
        total_comparisons = 0

        # 3. Bounded pairwise comparison within blocks
        for _block_key, block_mentions in blocks.items():
            n = len(block_mentions)
            for i in range(n):
                for j in range(i + 1, n):
                    if total_comparisons >= self.max_comparisons:
                        break

                    m1, m2 = block_mentions[i], block_mentions[j]

                    # Deduplicate pair check
                    pair_key = (
                        min(m1.mention_id, m2.mention_id),
                        max(m1.mention_id, m2.mention_id),
                    )
                    if pair_key in compared_pairs:
                        continue
                    compared_pairs.add(pair_key)
                    total_comparisons += 1

                    match_res = self.matcher.compare_mentions(m1, m2, run_id=run_id)
                    if match_res is not None:
                        candidate_matches.append(match_res)

                if total_comparisons >= self.max_comparisons:
                    break
            if total_comparisons >= self.max_comparisons:
                break

        # 4. Cluster mentions into ResolvedEntity groupings
        resolved_entities, unresolved = self._cluster_entities(case_id, mentions, candidate_matches)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return EntityResolutionResult(
            case_id=case_id,
            processing_run_id=run_id,
            total_mentions=len(mentions),
            total_comparisons=total_comparisons,
            candidate_matches=candidate_matches,
            resolved_entities=resolved_entities,
            unresolved_mentions=unresolved,
            blocking_summary=blocking_summary,
            execution_duration_ms=duration_ms,
        )

    def _compute_blocking_key(self, mention: EntityMention) -> str:
        """Compute deterministic indexing/blocking key for bounded comparisons."""
        t = mention.entity_type.value

        if mention.entity_type == ResolvedEntityType.ORGANIZATION:
            prefix = (mention.base_name or mention.normalized_value)[:3].strip().lower()
            return f"{t}:{prefix or 'none'}"

        if mention.entity_type == ResolvedEntityType.PERSON:
            prefix = (mention.base_name or mention.normalized_value)[:3].strip().lower()
            return f"{t}:{prefix or 'none'}"

        if mention.entity_type == ResolvedEntityType.TAX_IDENTIFIER:
            return f"{t}:{mention.jurisdiction or 'GEN'}:{mention.identifier_type or 'GEN'}"

        if mention.entity_type in (
            ResolvedEntityType.INVOICE_REFERENCE,
            ResolvedEntityType.TRANSACTION_REFERENCE,
        ):
            prefix = mention.normalized_value[:3].strip().upper()
            return f"{t}:{prefix or 'none'}"

        if mention.entity_type == ResolvedEntityType.BANK_ACCOUNT_REFERENCE:
            last4 = mention.normalized_value[-4:] if len(mention.normalized_value) >= 4 else "none"
            return f"{t}:{last4}"

        if mention.entity_type == ResolvedEntityType.CURRENCY_AMOUNT:
            return f"{t}:{mention.currency_code or 'UNKNOWN'}"

        return f"{t}:generic"

    def _cluster_entities(
        self,
        case_id: str,
        mentions: list[EntityMention],
        matches: list[EntityCandidateMatch],
    ) -> tuple[list[ResolvedEntity], list[EntityMention]]:
        """Group mentions into resolved entity clusters using connected components."""
        # Mentions index
        mention_map = {m.mention_id: m for m in mentions}

        # Graph of positive matches (exclude contradictions and weak ambiguous matches)
        adj: dict[str, set[str]] = collections.defaultdict(set)
        match_by_pair: dict[tuple[str, str], EntityCandidateMatch] = {}
        contradictions: set[tuple[str, str]] = set()

        for m in matches:
            pair = (
                min(m.target_mention_id, m.candidate_mention_id),
                max(m.target_mention_id, m.candidate_mention_id),
            )
            match_by_pair[pair] = m

            if m.match_classification == EntityMatchClassification.CONFLICTING_IDENTITY:
                contradictions.add(pair)
            elif (
                m.match_classification
                in (
                    EntityMatchClassification.EXACT_MATCH,
                    EntityMatchClassification.NORMALIZED_EXACT_MATCH,
                    EntityMatchClassification.STRONG_CANDIDATE,
                )
                and m.match_score >= self.cluster_threshold
                and m.decision_status != MatchDecisionStatus.REJECTED
            ):
                adj[m.target_mention_id].add(m.candidate_mention_id)
                adj[m.candidate_mention_id].add(m.target_mention_id)

        # Find connected components
        visited: set[str] = set()
        resolved_entities: list[ResolvedEntity] = []
        clustered_mention_ids: set[str] = set()

        for m_id, _mention in mention_map.items():
            if m_id in visited:
                continue

            # BFS / DFS to collect component
            queue = [m_id]
            component: list[str] = []
            visited.add(m_id)

            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        # Ensure no pair within candidate cluster is contradictory
                        has_contradiction = False
                        for existing in component:
                            pair = (min(existing, neighbor), max(existing, neighbor))
                            if pair in contradictions:
                                has_contradiction = True
                                break

                        if not has_contradiction:
                            visited.add(neighbor)
                            queue.append(neighbor)

            # If component has 2 or more mentions, create a ResolvedEntity
            if len(component) > 1:
                comp_mentions = [mention_map[cid] for cid in component]
                doc_ids = sorted({cm.document_id for cm in comp_mentions})

                # Collect match IDs
                cluster_match_ids: list[str] = []
                for i in range(len(component)):
                    for j in range(i + 1, len(component)):
                        pair = (min(component[i], component[j]), max(component[i], component[j]))
                        if pair in match_by_pair:
                            cluster_match_ids.append(match_by_pair[pair].id)

                # Canonical display name
                canonical_name = comp_mentions[0].original_value

                # Confidence: average of match scores
                scores = [
                    match_by_pair[
                        (min(component[i], component[j]), max(component[i], component[j]))
                    ].match_score
                    for i in range(len(component))
                    for j in range(i + 1, len(component))
                    if (min(component[i], component[j]), max(component[i], component[j]))
                    in match_by_pair
                ]
                avg_score = round(sum(scores) / len(scores), 4) if scores else 0.85

                resolved_entities.append(
                    ResolvedEntity(
                        id=generate_id(),
                        case_id=case_id,
                        entity_type=comp_mentions[0].entity_type,
                        canonical_name=canonical_name,
                        mention_ids=component,
                        document_ids=doc_ids,
                        confidence_score=avg_score,
                        is_confirmed=all(
                            match_by_pair[
                                (min(component[i], component[j]), max(component[i], component[j]))
                            ].match_classification
                            == EntityMatchClassification.EXACT_MATCH
                            for i in range(len(component))
                            for j in range(i + 1, len(component))
                            if (min(component[i], component[j]), max(component[i], component[j]))
                            in match_by_pair
                        ),
                        candidate_match_ids=cluster_match_ids,
                        metadata={
                            "cluster_size": len(component),
                            "document_count": len(doc_ids),
                        },
                    )
                )
                clustered_mention_ids.update(component)

        unresolved = [m for m in mentions if m.mention_id not in clustered_mention_ids]
        return resolved_entities, unresolved
