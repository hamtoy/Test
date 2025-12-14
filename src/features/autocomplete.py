"""Graph-Based Smart Autocomplete module.

Provides intelligent suggestions for next query types based on session history
and validates draft outputs against constraints from the knowledge graph.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from checks.detect_forbidden_patterns import find_violations
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class SmartAutocomplete:
    """그래프 기반 자동 완성/검증 보조.

    - 다음 질의 유형 추천
    - 출력 초안의 제약 위반 감지 및 제안
    """

    def __init__(self, kg: QAKnowledgeGraph):
        """Initialize the smart autocomplete system.

        Args:
            kg: QAKnowledgeGraph instance for graph queries.
        """
        self.kg = kg

    def suggest_next_query_type(
        self,
        current_session: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """현재 세션의 사용 타입/회수 기반으로 다음 질의 유형을 추천.

        session_limit를 초과한 유형은 제외, 사용되지 않은 유형 우선.
        """
        used_types = [t["type"] for t in current_session if t.get("type")]
        counts = {t: used_types.count(t) for t in set(used_types)}

        cypher = """
        MATCH (qt:QueryType)
        RETURN qt.name AS name, qt.korean AS korean, qt.session_limit AS limit, coalesce(qt.priority, 0) AS priority
        """
        graph_session = getattr(self.kg, "graph_session", None)
        if graph_session is None:
            # fallback for legacy stubs in tests
            graph = getattr(self.kg, "_graph", None)
            if graph is None:
                logger.debug("SmartAutocomplete: no graph_session/_graph; returning []")
                return []
            session_ctx = graph.session
        else:
            session_ctx = graph_session

        with session_ctx() as session:
            if session is None:
                logger.debug("SmartAutocomplete: graph unavailable, no suggestions")
                return []
            records = [dict(r) for r in session.run(cypher)]

        suggestions = []
        for r in records:
            limit = r.get("limit")
            if (
                limit is not None
                and isinstance(limit, int)
                and counts.get(r["name"], 0) >= limit
            ):
                continue
            if r["name"] in used_types:
                # 이미 사용된 타입은 우선순위를 낮게
                r["priority"] = r.get("priority", 0) - 1
            suggestions.append(r)

        # 우선순위 순 정렬 후 상위 3개 반환
        suggestions.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return suggestions[:3]

    def suggest_constraint_compliance(
        self,
        draft_output: str,
        query_type: str,
    ) -> dict[str, list[str]]:
        """출력 초안에 대해 제약 위반을 찾아 개선 제안을 반환.

        - 금지 패턴(그래프 + 로컬) 검사
        """
        violations: list[str] = []
        suggestions: list[str] = []

        # 로컬 금지 패턴 검사
        for v in find_violations(draft_output):
            violations.append(v["type"])
            suggestions.append(f"{v['match']} 표현을 제거하세요")

        # 그래프의 ErrorPattern 및 Constraint 패턴 검사
        graph_session = getattr(self.kg, "graph_session", None)
        if graph_session is None:
            graph = getattr(self.kg, "_graph", None)
            session_ctx = graph.session if graph is not None else None
        else:
            session_ctx = graph_session

        if session_ctx is None:
            logger.debug("SmartAutocomplete: graph unavailable, skip constraint checks")
            return {"violations": violations, "suggestions": suggestions}

        with session_ctx() as session:
            if session is None:
                logger.debug(
                    "SmartAutocomplete: graph unavailable, skip constraint checks",
                )
                return {"violations": violations, "suggestions": suggestions}
            ep_records = session.run(
                "MATCH (ep:ErrorPattern) RETURN ep.pattern AS pattern, ep.description AS desc",
            )
            for rec in ep_records:
                pat = rec["pattern"]
                if pat and re.search(pat, draft_output, flags=re.IGNORECASE):
                    violations.append(rec["desc"])
                    suggestions.append(f"패턴 '{pat}'를 제거하거나 수정하세요")

            # QueryType 관련 제약의 pattern 필드 검사 (있을 때만)
            cons_records = session.run(
                """
                MATCH (qt:QueryType {name: $qt})<-[:APPLIES_TO]-(r:Rule)-[:ENFORCES]->(c:Constraint)
                RETURN DISTINCT c.pattern AS pattern, c.description AS desc
                """,
                qt=query_type,
            )
            for rec in cons_records:
                pat = rec["pattern"]
                if pat and re.search(pat, draft_output, flags=re.IGNORECASE):
                    violations.append(rec["desc"])
                    suggestions.append(f"제약 '{rec['desc']}'을 준수하도록 수정하세요")

        return {"violations": violations, "suggestions": suggestions}
