from __future__ import annotations

import json
from typing import List, Dict, Optional

try:
    import redis
except ImportError:  # redis가 없을 때도 동작하도록
    redis = None

from qa_rag_system import QAKnowledgeGraph


class CachingLayer:
    """
    Rule 조회에 Redis 캐시를 덧붙이는 간단한 레이어.
    Redis가 없으면 그래프에서 직접 조회합니다.
    """

    def __init__(self, kg: QAKnowledgeGraph, redis_client: Optional["redis.Redis"] = None):
        self.kg = kg
        self.redis = redis_client if redis_client and redis else None

    def _fetch_rules_from_graph(self, query_type: str) -> List[Dict[str, str]]:
        cypher = """
        MATCH (r:Rule)-[:APPLIES_TO]->(qt:QueryType {name: $qt})
        RETURN r.id AS id, r.text AS text, r.section AS section
        """
        with self.kg._graph.session() as session:
            return [dict(rec) for rec in session.run(cypher, qt=query_type)]

    def get_rules_cached(self, query_type: str) -> List[Dict[str, str]]:
        """
        규칙 조회 + Redis 캐시 (1시간 TTL).
        """
        cache_key = f"rules:{query_type}"

        if self.redis:
            cached = self.redis.get(cache_key)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass

        rules = self._fetch_rules_from_graph(query_type)

        if self.redis:
            try:
                self.redis.setex(cache_key, 3600, json.dumps(rules, ensure_ascii=False))
            except Exception:
                pass

        return rules

    def invalidate_cache(self, pattern: str = "rules:*") -> int:
        """
        캐시 무효화. 삭제한 키 개수를 반환.
        """
        if not self.redis:
            return 0
        keys = self.redis.keys(pattern)
        if keys:
            return self.redis.delete(*keys)
        return 0
