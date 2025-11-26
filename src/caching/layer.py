from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol, Sequence, cast

try:
    import redis
except ImportError:  # redis가 없을 때도 동작하도록
    redis = None  # type: ignore[assignment]

from src.qa.rag_system import QAKnowledgeGraph


class _RedisClientProto(Protocol):
    def get(self, key: str) -> Any: ...

    def setex(self, key: str, ttl: int, value: str) -> Any: ...

    def keys(self, pattern: str) -> Sequence[Any]: ...

    def delete(self, *keys: Any) -> Any: ...


class CachingLayer:
    """
    Rule 조회에 Redis 캐시를 덧붙이는 간단한 레이어.
    Redis가 없으면 그래프에서 직접 조회합니다.
    """

    def __init__(
        self, kg: QAKnowledgeGraph, redis_client: Optional[_RedisClientProto] = None
    ):
        self.kg = kg
        self.redis = redis_client if redis_client and redis else None

    def _fetch_rules_from_graph(self, query_type: str) -> List[Dict[str, str]]:
        cypher = """
        MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
        RETURN r.id AS id, r.text AS text, r.section AS section
        """
        graph = getattr(self.kg, "_graph", None)
        if graph is None:
            return []
        with graph.session() as session:
            return cast(
                List[Dict[str, str]],
                [dict(rec) for rec in session.run(cypher, qt=query_type)],
            )

    def get_rules_cached(self, query_type: str) -> List[Dict[str, str]]:
        """
        규칙 조회 + Redis 캐시 (1시간 TTL).
        """
        cache_key = f"rules:{query_type}"

        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                try:
                    return cast(
                        List[Dict[str, str]], json.loads(cast(str | bytes, cached))
                    )
                except json.JSONDecodeError:
                    pass

        rules = self._fetch_rules_from_graph(query_type)

        if self.redis:
            try:
                self.redis.setex(cache_key, 3600, json.dumps(rules, ensure_ascii=False))
            except Exception as exc:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).warning("Cache write failed: %s", exc)

        return rules

    def invalidate_cache(self, pattern: str = "rules:*") -> int:
        """
        캐시 무효화. 삭제한 키 개수를 반환.
        """
        if not self.redis:
            return 0
        keys = list(self.redis.keys(pattern))
        if keys:
            deleted = self.redis.delete(*keys)
            return int(deleted) if isinstance(deleted, int) else 0
        return 0
