from __future__ import annotations

import logging
import re
from typing import Any, Dict

from src.qa.rag_system import QAKnowledgeGraph


class AdaptiveDifficultyAdjuster:
    """이미지 복잡도에 따라 질의/답변 난이도를 자동 조절합니다."""

    def __init__(self, kg: QAKnowledgeGraph):
        """Initialize the adaptive difficulty adjuster.

        Args:
            kg: QAKnowledgeGraph instance for graph queries.
        """
        self.kg = kg

    def analyze_text_complexity(self, text: str) -> Dict[str, Any]:
        """OCR 텍스트를 분석하여 복잡도를 추정합니다.

        Args:
            text: OCR 텍스트 문자열.

        Returns:
            complexity dict: text_density, has_structure, word_count, level 등.
        """
        if not text:
            return {
                "text_density": 0.0,
                "has_structure": False,
                "word_count": 0,
                "level": "simple",
                "recommended_turns": 3,
                "reasoning_possible": False,
            }

        # 기본 텍스트 분석
        words = text.split()
        word_count = len(words)
        char_count = len(text.replace(" ", ""))

        # 구조적 패턴 감지 (표, 숫자, 특수문자)
        has_table_pattern = bool(re.search(r"[\|┃┼━─]", text))
        has_numbers = bool(re.search(r"\d+[.,]?\d*%?", text))
        has_bullet = bool(re.search(r"[•·‧▪▸►→]", text))

        # 텍스트 밀도 계산 (단어 수 기반)
        # 짧은 텍스트: < 100 단어, 중간: 100-300, 복잡: > 300
        if word_count < 100:
            text_density = 0.3
        elif word_count < 300:
            text_density = 0.5
        else:
            text_density = 0.8

        # 복잡도 레벨 및 추론 가능성 결정
        if text_density < 0.4:
            level = "simple"
            recommended_turns = 3
            reasoning_possible = False  # 짧은 텍스트는 추론 불가
        elif text_density < 0.7:
            level = "medium"
            recommended_turns = 3
            reasoning_possible = True
        else:
            level = "complex"
            recommended_turns = 4
            reasoning_possible = True

        complexity: Dict[str, Any] = {
            "text_density": text_density,
            "has_structure": has_table_pattern or has_bullet,
            "has_numbers": has_numbers,
            "word_count": word_count,
            "char_count": char_count,
            "level": level,
            "recommended_turns": recommended_turns,
            "reasoning_possible": reasoning_possible,
        }

        return complexity

    def analyze_image_complexity(self, image_meta: Dict[str, Any]) -> Dict[str, Any]:
        """이미지 메타 정보를 기반으로 복잡도를 추정합니다.

        Args:
            image_meta: OCR/멀티모달 분석 결과 딕셔너리.

        Returns:
            complexity dict: text_density, has_structure, estimated_blocks, level 등.
        """
        complexity: Dict[str, Any] = {
            "text_density": float(image_meta.get("text_density", 0.5)),
            "has_structure": bool(image_meta.get("has_table_chart", False)),
            "estimated_blocks": 0.0,
            "reasoning_possible": True,
        }

        # Neo4j에서 유사한 text_density 페이지의 평균 블록 수 추정 (실패 시 무시)
        try:
            graph = getattr(self.kg, "_graph", None)
            if graph is None:
                raise RuntimeError("graph not available")
            with graph.session() as session:  # noqa: SLF001
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
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Failed to estimate blocks from graph: %s", exc
            )
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
        """복잡도에 따라 질의 요구사항을 조정합니다.

        Args:
            complexity: analyze_image_complexity 결과 딕셔너리.
            query_type: 질의 유형(explanation/reasoning 등).

        Returns:
            dict: 길이/깊이/증거 요구사항 등 조정값.
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
