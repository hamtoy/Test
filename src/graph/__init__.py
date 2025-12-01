"""Graph 패키지.

v3.0: 기존 import 경로는 더 이상 지원되지 않습니다.
    from src.graph import QAGraphBuilder                 # ✅ 신버전
"""

from __future__ import annotations

from .builder import QAGraphBuilder
from .data2neo_extractor import Data2NeoExtractor
from src.config.utils import require_env
from .entities import (
    DateEntity,
    DocumentRule,
    ExtractionResult,
    Organization,
    Person,
    Relationship,
)
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
    "Data2NeoExtractor",
    "Person",
    "Organization",
    "DateEntity",
    "DocumentRule",
    "Relationship",
    "ExtractionResult",
    "QUERY_TYPES",
    "CONSTRAINTS",
    "TEMPLATES",
    "ERROR_PATTERNS",
    "BEST_PRACTICES",
    "CONSTRAINT_KEYWORDS",
    "QUERY_TYPE_KEYWORDS",
    "EXAMPLE_RULE_MAPPINGS",
]
