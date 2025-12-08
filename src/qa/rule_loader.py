"""Neo4j 규칙 로더 - 전역 캐싱 버전."""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)

# 전역 KG 참조 (프로세스 단위)
_GLOBAL_KG: QAKnowledgeGraph | None = None


def set_global_kg(kg: QAKnowledgeGraph | None) -> None:
    """전역 KG 설정 (앱 초기화 시 1회 호출)."""
    global _GLOBAL_KG
    _GLOBAL_KG = kg
    logger.info("Global KG set for RuleLoader cache: %s", kg is not None)


@lru_cache(maxsize=128)
def _load_rules_from_global_kg(query_type: str) -> tuple[str, ...]:
    """전역 KG에서 규칙을 로드하고 전역 캐시에 저장."""
    if _GLOBAL_KG is None:
        logger.debug("Global KG not set; returning defaults for type=%s", query_type)
        return tuple()

    try:
        kg_rules = _GLOBAL_KG.get_rules_for_query_type(query_type)
        rules = [
            text for text in (r.get("text") for r in kg_rules) if isinstance(text, str)
        ]
        logger.debug(
            "Loaded %d rules for type=%s from Neo4j (global cache)",
            len(rules),
            query_type,
        )
        return tuple(rules)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Rule load failed for type=%s: %s", query_type, exc)
        return tuple()


def clear_global_rule_cache() -> None:
    """전역 규칙 캐시 초기화."""
    _load_rules_from_global_kg.cache_clear()
    logger.info("Global rule cache cleared")


def get_global_cache_info() -> dict[str, float | int | None]:
    """전역 캐시 통계 반환."""
    info = _load_rules_from_global_kg.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "maxsize": info.maxsize,
        "currsize": info.currsize,
        "hit_rate": (
            info.hits / (info.hits + info.misses)
            if (info.hits + info.misses) > 0
            else 0.0
        ),
    }


class RuleLoader:
    """전역 캐싱을 사용하는 규칙 로더."""

    def __init__(self, kg: QAKnowledgeGraph | None) -> None:
        """기존 인터페이스 호환을 위해 KG를 받아 초기화."""
        # kg 파라미터는 기존 코드와의 호환성을 위해 유지
        self.kg = kg

    def get_rules_for_type(
        self,
        query_type: str,
        default_rules: list[str],
    ) -> list[str]:
        """지정된 질의 유형의 규칙을 반환 (전역 캐시 사용)."""
        cached_rules = _load_rules_from_global_kg(query_type)
        if cached_rules:
            return list(cached_rules)
        return list(default_rules)

    def clear_cache(self) -> None:
        """전역 캐시 초기화 래퍼."""
        clear_global_rule_cache()

    def get_cache_info(self) -> dict[str, float | int | None]:
        """전역 캐시 통계 래퍼."""
        return get_global_cache_info()
