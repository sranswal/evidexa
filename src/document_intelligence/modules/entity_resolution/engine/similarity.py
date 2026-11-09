"""Deterministic string and token similarity metrics for entity resolution."""

from __future__ import annotations

import difflib
import re


def calculate_string_similarity(s1: str, s2: str) -> float:
    """Calculate deterministic character-level SequenceMatcher similarity ratio in [0.0, 1.0]."""
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    return round(difflib.SequenceMatcher(None, s1, s2).ratio(), 4)


def calculate_token_set_similarity(s1: str, s2: str) -> float:
    """Calculate deterministic token set Jaccard/overlap similarity in [0.0, 1.0]."""
    tokens1 = set(re.findall(r"\w+", s1.lower()))
    tokens2 = set(re.findall(r"\w+", s2.lower()))

    if not tokens1 or not tokens2:
        return 0.0
    if tokens1 == tokens2:
        return 1.0

    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)

    return round(len(intersection) / len(union), 4)


def compute_composite_name_similarity(s1: str, s2: str) -> float:
    """Compute combined character and token similarity for organization/person names.

    Weighted formula: 0.5 * sequence_matcher + 0.5 * token_set_similarity.
    Returns float in [0.0, 1.0].
    """
    if s1 == s2:
        return 1.0
    char_sim = calculate_string_similarity(s1, s2)
    tok_sim = calculate_token_set_similarity(s1, s2)
    return round(0.5 * char_sim + 0.5 * tok_sim, 4)
