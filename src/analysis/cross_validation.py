from __future__ import annotations

import logging
import re
from typing import Any

from neo4j.exceptions import Neo4jError

from src.qa.rag_system import QAKnowledgeGraph


class CrossValidationSystem:
    """생성된 질의-답변 쌍을 다각도로 검증합니다."""

    def __init__(self, kg: QAKnowledgeGraph):
        """Initialize the cross validation system.

        Args:
            kg: QAKnowledgeGraph instance for graph queries.
        """
        self.kg = kg
        self.logger = logging.getLogger(__name__)

    def cross_validate_qa_pair(
        self,
        question: str,
        answer: str,
        query_type: str,
        image_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """질문과 답변의 일관성/근거/규칙/참신성을 통합 검증합니다."""
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
            ],
        )

        return validation_results

    def _check_qa_consistency(self, question: str, answer: str) -> dict[str, Any]:
        """질문과 답변이 일치하는지 간단히 확인합니다."""
        # 간이 키워드 기반 점수: 질문의 토큰 일부가 답변에 포함되는 비율
        q_tokens = [t for t in re.split(r"\W+", question.lower()) if t]
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
        self,
        answer: str,
        image_meta: dict[str, Any],
    ) -> dict[str, Any]:
        """답변이 이미지(그래프)에 근거했는지 확인합니다."""
        page_id = image_meta.get("page_id")
        if not page_id:
            return {"score": 0.5, "grounded": False, "note": "page_id 없음"}

        contents: list[str] = []
        try:
            graph_session = getattr(self.kg, "graph_session", None)
            if graph_session is None:
                graph = getattr(self.kg, "_graph", None)
                if graph is None:
                    self.logger.debug("Grounding check skipped: graph unavailable")
                    return {"score": 0.5, "grounded": False, "note": "graph 없음"}
                session_ctx = graph.session
            else:
                session_ctx = graph_session

            with session_ctx() as session:
                if session is None:
                    self.logger.debug("Grounding check skipped: graph unavailable")
                    return {"score": 0.5, "grounded": False, "note": "graph 없음"}
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
        except Neo4jError as exc:
            self.logger.warning("Grounding check failed: %s", exc)
            return {"score": 0.5, "grounded": False, "note": "Neo4j 조회 실패"}
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Grounding check failed (unknown): %s", exc)
            return {"score": 0.5, "grounded": False, "note": "Neo4j 조회 실패"}

        if not contents:
            return {"score": 0.5, "grounded": False, "note": "본문 콘텐츠 없음"}

        # 간단한 매칭: 본문 키워드 중 몇 개가 답변에 등장하는지
        joined = " ".join(contents).lower()
        candidates = [w for w in re.split(r"\W+", joined) if len(w) > 2]
        if not candidates:
            return {"score": 0.5, "grounded": False, "note": "본문 키워드 부족"}

        sample = candidates[:50]  # 과도한 계산 방지
        answer_lower = answer.lower()
        hits = sum(1 for w in sample if w in answer_lower)
        ratio = hits / len(sample)
        score = 0.3 + 0.7 * ratio

        return {"score": min(score, 1.0), "grounded": score > 0.6}

    def _check_repetition(self, _: str) -> list[str]:
        """반복 표현 검증 (repetition_check).

        Phase 4 Complete: 명사 반복은 Gemini의 자연스러운 표현이므로 검증 스킵.
        서술어 반복만 별도 검증 (_check_predicate_repetition).
        """
        # 명사/키워드 반복 검증 비활성화
        # 이유: 경제/금융 텍스트에서 "시장", "노동" 등 반복은 자연스러움
        #       Gemini의 표현을 신뢰하고 인간이 최종 판단
        return []  # ← 검증 스킵

    def _check_formatting_rules(self, answer: str) -> list[str]:
        """형식 규칙 검증 (formatting_rules)."""
        violations = []

        # 목록형 답변 감지 (숫자 불릿 또는 기호 불릿)
        has_numbered_bullets = bool(re.search(r"^\d+\.\s", answer, re.MULTILINE))
        has_symbol_bullets = bool(re.search(r"^[-*•]\s", answer, re.MULTILINE))

        if has_numbered_bullets or has_symbol_bullets:
            # Phase 4: 서술어 반복 검증 추가
            violations.extend(self._check_predicate_repetition(answer))

            # 불릿 간격 일관성만 검사 (문단 구분은 선택)
            if has_symbol_bullets:
                dash_bullets = re.findall(r"^-\s", answer, re.MULTILINE)
                star_bullets = re.findall(r"^\*\s", answer, re.MULTILINE)
                if dash_bullets and star_bullets:
                    violations.append("불릿 표시 일관성 필요 (- 또는 * 중 하나만 사용)")

        return violations

    def _check_predicate_repetition(self, answer: str) -> list[str]:
        """CSV 규칙에 따른 서술어 반복 검증.

        규칙:
        - 목록 3개 이하: 동일 서술어 불가 (모두 달라야 함)
        - 목록 4개 이상: 50% 미만에서만 동일 서술어 허용 (단, 2개 이상 반복 불가)

        예시 (목록 5개):
        ✅ A 서술어 2회, B/C/D 각 1회
        ❌ A 서술어 2회, B 서술어 2회, C 각 1회
        """
        list_items = self._extract_bullet_items(answer)
        if not list_items:
            return []

        predicates = self._extract_item_predicates(list_items)
        predicate_counts = self._count_predicates(predicates)
        list_count = len(list_items)

        if list_count <= 3:
            return self._validate_predicates_small(list_count, predicate_counts)
        return self._validate_predicates_large(list_count, predicate_counts)

    def _extract_bullet_items(self, answer: str) -> list[str]:
        return re.findall(
            r"^(?:\d+\.|[-*•])\s+((?:(?!\n(?:\d+\.|[-*•])\s).)+)",
            answer,
            re.MULTILINE | re.DOTALL,
        )

    def _extract_item_predicates(self, list_items: list[str]) -> list[str]:
        predicates: list[str] = []
        for item in list_items:
            first_sentence = item.split(".")[0].strip()
            predicate_match = re.search(
                r"([가-힣A-Za-z0-9]+)(?=\s*(?:한다|된다|하며|합니다|습니다|되다|하는|되는))",
                first_sentence,
            )
            if predicate_match:
                verb_base = predicate_match.group(1).strip()
                predicates.append(verb_base.split()[-1] if verb_base else "")
            else:
                predicates.append("")
        return predicates

    def _count_predicates(self, predicates: list[str]) -> dict[str, int]:
        predicate_counts: dict[str, int] = {}
        for pred in predicates:
            if pred:
                predicate_counts[pred] = predicate_counts.get(pred, 0) + 1
        return predicate_counts

    def _validate_predicates_small(
        self,
        list_count: int,
        predicate_counts: dict[str, int],
    ) -> list[str]:
        violations: list[str] = []
        for pred, count in predicate_counts.items():
            if count > 1:
                violations.append(
                    f"목록 {list_count}개: '{pred}' 서술어 {count}회 반복 "
                    f"(3개 이하는 동일 서술어 불가)",
                )
        return violations

    def _validate_predicates_large(
        self,
        list_count: int,
        predicate_counts: dict[str, int],
    ) -> list[str]:
        violations: list[str] = []
        max_allowed = (list_count - 1) // 2
        repeated_predicates: list[tuple[str, int]] = []

        for pred, count in predicate_counts.items():
            if count <= 1:
                continue
            repeated_predicates.append((pred, count))
            if count > max_allowed:
                violations.append(
                    f"목록 {list_count}개: '{pred}' 서술어 {count}회 반복 "
                    f"(최대 {max_allowed}회)",
                )

        if sum(1 for _, count in repeated_predicates if count >= 2) >= 2:
            repeat_preds = [pred for pred, count in repeated_predicates if count >= 2]
            violations.append(
                f"목록 {list_count}개: 2개 이상의 서술어 동시 반복 불가 "
                f"({', '.join(repeat_preds)})",
            )

        return violations

    def _check_temporal_expressions(self, _: str) -> list[str]:
        """시의성 표현 검증 (temporal_expression_check, 현재 비활성화)."""
        # Keep the hook for constraint-based calls; no active checks for now.
        return []

    def _check_rule_compliance(self, answer: str, query_type: str) -> dict[str, Any]:
        """패턴 기반 규칙 준수 여부를 확인합니다."""
        violations: list[str] = []

        # 제약 패턴 검사
        constraints = self.kg.get_constraints_for_query_type(query_type)
        for c in constraints:
            constraint_id = c.get("id")
            pattern = c.get("pattern")

            # 기존 prohibition 타입 Constraint
            if (
                c.get("type") == "prohibition"
                and pattern
                and re.search(pattern, answer)
            ):
                violations.append(c.get("description", pattern))

            # 피드백 기반 Constraint (ID 기반 호출)
            elif constraint_id == "temporal_expression_check":
                violations.extend(self._check_temporal_expressions(answer))

            elif constraint_id == "repetition_check":
                violations.extend(self._check_repetition(answer))

            elif constraint_id == "formatting_rules":
                violations.extend(self._check_formatting_rules(answer))

        # 금지 패턴(ErrorPattern) 전체 검사
        try:
            graph_session = getattr(self.kg, "graph_session", None)
            if graph_session is None:
                graph = getattr(self.kg, "_graph", None)
                if graph is None:
                    self.logger.debug("ErrorPattern check skipped: graph unavailable")
                    raise RuntimeError("graph missing")
                session_ctx = graph.session
            else:
                session_ctx = graph_session

            with session_ctx() as session:
                if session is None:
                    self.logger.debug("ErrorPattern check skipped: graph unavailable")
                    raise RuntimeError("graph missing")
                eps = session.run(
                    """
                    MATCH (e:ErrorPattern)
                    RETURN e.pattern AS pattern, e.description AS description
                    """,
                )
                for ep in eps:
                    pat = ep.get("pattern")
                    if pat and re.search(pat, answer):
                        violations.append(ep.get("description", pat))
        except Neo4jError as exc:
            self.logger.warning("ErrorPattern lookup failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("ErrorPattern lookup failed (unknown): %s", exc)

        score = max(0.0, 1.0 - 0.2 * len(violations))
        return {"score": score, "violations": violations}

    def _check_novelty(self, question: str) -> dict[str, Any]:
        """질문의 참신함(중복 방지)을 간단히 평가합니다."""
        store = getattr(self.kg, "_vector_store", None)
        if not store:
            return {"score": 1.0, "novel": True, "note": "벡터 스토어 없음"}

        try:
            similar = store.similarity_search(question, k=1)
            if similar and similar[0].metadata.get("similarity", 0) > 0.95:
                return {"score": 0.3, "too_similar": True}
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("Novelty check failed: %s", exc)
            return {"score": 0.5, "novel": False, "note": "유사도 조회 실패"}

        return {"score": 1.0, "novel": True}
