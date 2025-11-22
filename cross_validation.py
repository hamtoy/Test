from __future__ import annotations

import re
from typing import Any, Dict, List

from qa_rag_system import QAKnowledgeGraph


class CrossValidationSystem:
    """
    생성된 질의-답변 쌍을 다각도로 검증합니다.
    """

    def __init__(self, kg: QAKnowledgeGraph):
        self.kg = kg

    def cross_validate_qa_pair(
        self, question: str, answer: str, query_type: str, image_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        질문과 답변의 일관성/근거/규칙/참신성을 통합 검증합니다.
        """

        validation_results = {
            "consistency": self._check_qa_consistency(question, answer),
            "groundedness": self._check_image_grounding(answer, image_meta),
            "rule_compliance": self._check_rule_compliance(answer, query_type),
            "novelty": self._check_novelty(question),
        }

        validation_results["overall_score"] = sum(
            [
                validation_results["consistency"]["score"] * 0.3,
                validation_results["groundedness"]["score"] * 0.3,
                validation_results["rule_compliance"]["score"] * 0.3,
                validation_results["novelty"]["score"] * 0.1,
            ]
        )

        return validation_results

    def _check_qa_consistency(self, question: str, answer: str) -> Dict[str, Any]:
        """질문과 답변이 일치하는지 간단히 확인합니다."""

        # 간이 키워드 기반 점수: 질문의 토큰 일부가 답변에 포함되는 비율
        q_tokens = [t for t in re.split(r"\\W+", question.lower()) if t]
        if not q_tokens:
            return {"score": 0.5, "explanation": "질문 토큰이 없음"}

        hits = sum(1 for t in q_tokens if t in answer.lower())
        ratio = hits / len(q_tokens)
        score = 0.3 + 0.7 * ratio  # 최소 0.3 보정

        return {
            "score": min(score, 1.0),
            "explanation": f"질문 토큰 매칭 비율: {ratio:.2f}",
        }

    def _check_image_grounding(
        self, answer: str, image_meta: Dict[str, Any]
    ) -> Dict[str, Any]:
        """답변이 이미지(그래프)에 근거했는지 확인합니다."""

        page_id = image_meta.get("page_id")
        if not page_id:
            return {"score": 0.5, "grounded": False, "note": "page_id 없음"}

        contents: List[str] = []
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                result = session.run(
                    """
                    MATCH (p:Page {id: $page_id})-[:CONTAINS*]->(b:Block)
                    RETURN collect(b.content) AS all_content
                    """,
                    page_id=page_id,
                ).single()
                contents = (
                    result["all_content"] if result and result["all_content"] else []
                )
        except Exception:
            return {"score": 0.5, "grounded": False, "note": "Neo4j 조회 실패"}

        if not contents:
            return {"score": 0.5, "grounded": False, "note": "본문 콘텐츠 없음"}

        # 간단한 매칭: 본문 키워드 중 몇 개가 답변에 등장하는지
        joined = " ".join(contents).lower()
        candidates = [w for w in re.split(r"\\W+", joined) if len(w) > 2]
        if not candidates:
            return {"score": 0.5, "grounded": False, "note": "본문 키워드 부족"}

        sample = candidates[:50]  # 과도한 계산 방지
        hits = sum(1 for w in sample if w in answer.lower())
        ratio = hits / len(sample)
        score = 0.3 + 0.7 * ratio

        return {"score": min(score, 1.0), "grounded": score > 0.6}

    def _check_rule_compliance(self, answer: str, query_type: str) -> Dict[str, Any]:
        """패턴 기반 규칙 준수 여부를 확인합니다."""

        violations: List[str] = []

        # 제약 패턴 검사
        constraints = self.kg.get_constraints_for_query_type(query_type)
        for c in constraints:
            pattern = c.get("pattern")
            if (
                c.get("type") == "prohibition"
                and pattern
                and re.search(pattern, answer)
            ):
                violations.append(c.get("description", pattern))

        # 금지 패턴(ErrorPattern) 전체 검사
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                eps = session.run(
                    """
                    MATCH (e:ErrorPattern)
                    RETURN e.pattern AS pattern, e.description AS description
                    """
                )
                for ep in eps:
                    pat = ep.get("pattern")
                    if pat and re.search(pat, answer):
                        violations.append(ep.get("description", pat))
        except Exception:
            pass

        score = max(0.0, 1.0 - 0.2 * len(violations))
        return {"score": score, "violations": violations}

    def _check_novelty(self, question: str) -> Dict[str, Any]:
        """질문의 참신함(중복 방지)을 간단히 평가합니다."""

        store = getattr(self.kg, "_vector_store", None)
        if not store:
            return {"score": 1.0, "novel": True, "note": "벡터 스토어 없음"}

        try:
            similar = store.similarity_search(question, k=1)
            if similar and similar[0].metadata.get("similarity", 0) > 0.95:
                return {"score": 0.3, "too_similar": True}
        except Exception:
            return {"score": 0.5, "novel": False, "note": "유사도 조회 실패"}

        return {"score": 1.0, "novel": True}
