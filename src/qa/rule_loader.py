"""Neo4j 규칙/제약 로더 유틸."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class RuleLoader:
    """Neo4j 규칙 로더 (간단 캐싱 포함)."""

    def __init__(self, kg: Optional[QAKnowledgeGraph]) -> None:
        self.kg = kg
        self._cache: Dict[str, List[str]] = {}

    def get_rules_for_type(
        self, query_type: str, default_rules: List[str]
    ) -> List[str]:
        """지정된 질의 유형의 규칙을 반환하고 캐시합니다."""
        if query_type in self._cache:
            return self._cache[query_type]

        rules: List[str] = []

        if self.kg is not None:
            try:
                constraints = self.kg.get_constraints_for_query_type(query_type)
                rules = [
                    c.get("description") for c in constraints if c.get("description")
                ]
            except Exception as exc:  # noqa: BLE001
                logger.debug("규칙 로드 실패 (폴백 사용): %s", exc)

        if not rules:
            rules = list(default_rules)

        self._cache[query_type] = rules
        return rules

    def clear_cache(self) -> None:
        """캐시 초기화."""
        self._cache.clear()
