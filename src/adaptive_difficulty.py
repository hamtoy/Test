from __future__ import annotations

from typing import Any, Dict

from src.qa_rag_system import QAKnowledgeGraph


class AdaptiveDifficultyAdjuster:
    """
    이미지 복잡도에 따라 질의/답변 난이도를 자동 조절합니다.
    """

    def __init__(self, kg: QAKnowledgeGraph):
        self.kg = kg

    def analyze_image_complexity(self, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        """
        이미지 메타 정보를 기반으로 복잡도를 추정합니다.
        """

        complexity: Dict[str, Any] = {
            "text_density": float(image_meta.get("text_density", 0.5)),
            "has_structure": bool(image_meta.get("has_table_chart", False)),
            "estimated_blocks": 0.0,
            "reasoning_possible": True,
        }

        # Neo4j에서 유사한 text_density 페이지의 평균 블록 수 추정 (실패 시 무시)
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                result = session.run(
                    """
                    MATCH (p:Page)
                    WHERE exists(p.text_density)
                      AND p.text_density > $density - 0.1
                      AND p.text_density < $density + 0.1
                    OPTIONAL MATCH (p)-[:CONTAINS*]->(b:Block)
                    WITH p, count(DISTINCT b) AS blocks
                    RETURN avg(blocks) AS avg_blocks
                    """,
                    density=complexity["text_density"],
                )
                record = result.single()
                if record:
                    avg_blocks = record.get("avg_blocks")
                    if avg_blocks is not None:
                        complexity["estimated_blocks"] = float(avg_blocks)
        except Exception:
            pass  # 그래프 접근 실패 시 기본값 유지

        # 복잡도 레벨 결정
        if complexity["text_density"] < 0.4:
            complexity["level"] = "simple"
            complexity["recommended_turns"] = 3
            complexity["reasoning_possible"] = False
        elif complexity["text_density"] < 0.7:
            complexity["level"] = "medium"
            complexity["recommended_turns"] = 3
        else:
            complexity["level"] = "complex"
            complexity["recommended_turns"] = 4

        return complexity

    def adjust_query_requirements(
        self, complexity: Dict[str, Any], query_type: str
    ) -> Dict[str, Any]:
        """
        복잡도에 따라 질의 요구사항을 조정합니다.
        """

        adjustments: Dict[str, Any] = {}

        if query_type == "explanation":
            if complexity.get("level") == "simple":
                adjustments.update(
                    {"min_length": 100, "max_length": 300, "depth": "shallow"}
                )
            elif complexity.get("level") == "complex":
                adjustments.update(
                    {"min_length": 300, "max_length": 800, "depth": "deep"}
                )

        elif query_type == "reasoning":
            if not complexity.get("reasoning_possible", True):
                adjustments["fallback"] = "target"  # 추론 불가 시 타겟으로 변경
            else:
                adjustments["evidence_required"] = True

        return adjustments
