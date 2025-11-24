from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.qa_rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class DynamicExampleSelector:
    """
    현재 상황에 가장 적합한 예시를 그래프에서 선택.
    """

    def __init__(self, kg: QAKnowledgeGraph):
        self.kg = kg

    def select_best_examples(
        self, query_type: str, context: Dict[str, Any], k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        컨텍스트에 맞는 최적 예시 선택.
        """

        examples: List[Dict[str, Any]] = []
        try:
            with self.kg.graph_session() as session:  # type: ignore[union-attr]
                if session is None:
                    return []
                conditions = []
                params: Dict[str, Any] = {"query_type": query_type, "k": k}

                if context.get("has_table_chart"):
                    conditions.append("e.context_has_table = true")

                if context.get("text_density") is not None:
                    conditions.append("e.text_density > $min_density")
                    params["min_density"] = float(context["text_density"]) - 0.2

                where_parts = [
                    "e.type = 'positive'",
                    "coalesce(e.success_rate, 0) > 0.8",
                ]
                where_parts.extend(conditions)
                where_clause = " AND ".join(where_parts)

                cypher = f"""
                MATCH (qt:QueryType {{name: $query_type}})
                MATCH (qt)<-[:FOR_TYPE]-(e:Example)
                WHERE {where_clause}
                RETURN e.text AS example,
                       coalesce(e.success_rate, 0) AS rate,
                       coalesce(e.usage_count, 0) AS usage
                ORDER BY rate DESC, usage ASC
                LIMIT $k
                """

                result = session.run(cypher, **params)

                examples = result.data()

                # 다양성 확보: 사용 횟수 업데이트
                for ex in examples:
                    session.run(
                        """
                        MATCH (e:Example {text: $text})
                        SET e.usage_count = coalesce(e.usage_count, 0) + 1
                        """,
                        text=ex["example"],
                    )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Example selection failed: %s", exc)
            examples = []

        return examples
