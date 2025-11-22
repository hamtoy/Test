from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List

from qa_rag_system import QAKnowledgeGraph


class RealTimeConstraintEnforcer:
    """
    생성 중간에 실시간으로 제약 조건을 체크하고 수정 제안을 반환합니다.
    """

    def __init__(self, kg: QAKnowledgeGraph):
        self.kg = kg

    def stream_with_validation(self, generator: Iterable[str], query_type: str):
        """
        LLM 출력을 스트리밍하면서 실시간 검증.
        chunk 단위로 content/violation 이벤트를 생성합니다.
        """

        buffer = ""

        constraints = self.kg.get_constraints_for_query_type(query_type)

        for chunk in generator:
            buffer += chunk

            # 실시간 금지 패턴 체크
            for constraint in constraints:
                if constraint["type"] == "prohibition":
                    pattern = constraint.get("pattern", "")
                    if pattern and re.search(pattern, buffer):
                        yield {
                            "type": "violation",
                            "constraint": constraint.get("description", ""),
                            "suggestion": f"'{pattern}' 표현을 제거해주세요",
                        }
                        return

            yield {"type": "content", "text": chunk}

        # 최종 검증 결과
        final_check = self.validate_complete_output(buffer, query_type)
        yield {"type": "final_validation", "result": final_check}

    def validate_complete_output(
        self, output: str, query_type: str
    ) -> Dict[str, object]:
        """완성된 출력의 종합 검증."""

        issues: List[str] = []

        # 1. 마크다운 규칙 체크
        if query_type in ["explanation", "summary"]:
            if not re.search(r"\*\*[^*]+\*\*", output):
                issues.append("볼드체(**) 사용이 부족합니다")

            if re.search(r"\d{4}\s*-\s*\d{4}", output):
                issues.append(
                    "기간 표기에 공백이 있습니다. 하이픈만 사용하세요: 2023-2024"
                )

        # 2. 문장 재구성 체크 (간이)
        if query_type in ["explanation", "summary"]:
            for block in self._get_original_blocks():
                similarity = self._calculate_similarity(
                    output, block.get("content", "")
                )
                if similarity > 0.9:  # 너무 유사
                    issues.append(
                        f"원문과 너무 유사: '{block.get('content', '')[:50]}...'"
                    )

        return {"valid": len(issues) == 0, "issues": issues}

    def _get_original_blocks(self) -> List[Dict[str, str]]:
        """
        원문 블록을 일부 조회하여 유사도 검증에 사용.
        Neo4j 연결에 실패하면 빈 리스트를 반환합니다.
        """

        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                result = session.run(
                    """
                    MATCH (b:Block)
                    RETURN b.content AS content
                    LIMIT 20
                    """
                )
                return [dict(r) for r in result]
        except Exception:
            return []

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """간단한 유사도 계산 (실제로는 더 정교하게)."""

        return SequenceMatcher(None, text1, text2).ratio()
