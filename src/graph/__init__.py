"""Graph 패키지.

v3.0: 기존 import 경로는 더 이상 지원되지 않습니다.
    from src.graph import QAGraphBuilder                 # ✅ 신버전
"""

from __future__ import annotations

from src.config.utils import require_env

from .builder import QAGraphBuilder
from .data2neo_extractor import Data2NeoExtractor
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
    "BEST_PRACTICES",
    "CONSTRAINTS",
    "CONSTRAINT_KEYWORDS",
    "ERROR_PATTERNS",
    "EXAMPLE_RULE_MAPPINGS",
    "QUERY_TYPES",
    "QUERY_TYPE_KEYWORDS",
    "TEMPLATES",
    "Data2NeoExtractor",
    "DateEntity",
    "DocumentRule",
    "ExtractionResult",
    "Organization",
    "Person",
    "QAGraphBuilder",
    "Relationship",
    "require_env",
]
