"""Deterministic cross-case correlation engine with blocking and bounded execution."""

from __future__ import annotations

import collections
import time

from document_intelligence.domain.models.cross_case import (
    CrossCaseCandidateMatch,
    CrossCaseCorrelationResult,
)
from document_intelligence.domain.models.entity_resolution import EntityMention
from document_intelligence.modules.cross_case.matcher import CrossCaseMatcher


class CrossCaseCorrelationEngine:
    """Orchestrates deterministic candidate matching across authorized cases."""

    def __init__(
        self,
        matcher: CrossCaseMatcher | None = None,
        max_comparisons: int = 10000,
        max_matches_limit: int = 500,
    ) -> None:
        self.matcher = matcher or CrossCaseMatcher()
        self.max_comparisons = max_comparisons
        self.max_matches_limit = max_matches_limit

    def correlate(
        self,
        scope_id: str,
        organization_id: str,
        mentions: list[EntityMention],
        case_ids: list[str],
    ) -> CrossCaseCorrelationResult:
        """Execute deterministic correlation across entity mentions from authorized cases."""
        start_time = time.perf_counter()

        # 1. Deterministic blocking to partition mentions by type and prefix
        blocks: dict[str, list[EntityMention]] = collections.defaultdict(list)
        for m in mentions:
            val = (m.normalized_value or m.original_value or "").strip().lower()
            prefix = val[:4] if len(val) >= 4 else val
            key = f"{m.entity_type.value}:{prefix}"
            blocks[key].append(m)

        candidate_matches: list[CrossCaseCandidateMatch] = []
        compared_pairs: set[tuple[str, str]] = set()
        total_comparisons = 0

        # 2. Bounded comparison across cases within blocks
        for _block_key, block_mentions in blocks.items():
            n = len(block_mentions)
            if n < 2:
                continue

            for i in range(n):
                m1 = block_mentions[i]
                for j in range(i + 1, n):
                    m2 = block_mentions[j]

                    # Enforce cross-case comparison only
                    if m1.case_id == m2.case_id:
                        continue

                    # Avoid duplicate pair comparisons
                    pair_id: tuple[str, str] = (
                        (m1.mention_id, m2.mention_id)
                        if m1.mention_id < m2.mention_id
                        else (m2.mention_id, m1.mention_id)
                    )
                    if pair_id in compared_pairs:
                        continue
                    compared_pairs.add(pair_id)

                    total_comparisons += 1
                    if total_comparisons > self.max_comparisons:
                        break

                    candidate = self.matcher.compare(
                        m1=m1, m2=m2, scope_id=scope_id, organization_id=organization_id
                    )
                    if candidate:
                        candidate_matches.append(candidate)
                        if len(candidate_matches) >= self.max_matches_limit:
                            break

                if total_comparisons > self.max_comparisons:
                    break
            if total_comparisons > self.max_comparisons:
                break

        # Sort candidate matches by match score descending
        candidate_matches.sort(key=lambda m: m.match_score, reverse=True)

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return CrossCaseCorrelationResult(
            scope_id=scope_id,
            organization_id=organization_id,
            cases_analyzed=case_ids,
            total_mentions_compared=total_comparisons,
            candidate_matches=candidate_matches,
            execution_duration_ms=round(duration_ms, 2),
        )
