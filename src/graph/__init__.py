"""Graph 패키지.

기존 import 경로 유지:
    from src.graph_schema_builder import QAGraphBuilder  # ❌ 구버전
    from src.graph import QAGraphBuilder                 # ✅ 신버전
"""

from __future__ import annotations

from .builder import QAGraphBuilder, require_env
from .mappings import (
    CONSTRAINT_KEYWORDS,
    EXAMPLE_RULE_MAPPINGS,
    QUERY_TYPE_KEYWORDS,
)
from .schema import (
    BEST_PRACTICES,
    CONSTRAINTS,
    ERROR_PATTERNS,
    QUERY_TYPES,
    TEMPLATES,
)

__all__ = [
    "QAGraphBuilder",
    "require_env",
    "QUERY_TYPES",
    "CONSTRAINTS",
    "TEMPLATES",
    "ERROR_PATTERNS",
    "BEST_PRACTICES",
    "CONSTRAINT_KEYWORDS",
    "QUERY_TYPE_KEYWORDS",
    "EXAMPLE_RULE_MAPPINGS",
]
