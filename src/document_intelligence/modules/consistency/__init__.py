"""Cross-document consistency analysis module exports."""

from document_intelligence.modules.consistency.context import ConsistencyContext
from document_intelligence.modules.consistency.engine import (
    ConsistencyAnalysisEngine,
    ConsistencyRuleRegistry,
    default_consistency_rule_registry,
)
from document_intelligence.modules.consistency.financial import (
    compare_monetary_amounts,
    parse_decimal,
)
from document_intelligence.modules.consistency.rules.base import BaseConsistencyRule

__all__ = [
    "ConsistencyContext",
    "ConsistencyAnalysisEngine",
    "ConsistencyRuleRegistry",
    "default_consistency_rule_registry",
    "BaseConsistencyRule",
    "parse_decimal",
    "compare_monetary_amounts",
]
