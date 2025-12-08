from __future__ import annotations

import importlib
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
        hits = sum(1 for w in sample if w in answer.lower())
        ratio = hits / len(sample)
        score = 0.3 + 0.7 * ratio

        return {"score": min(score, 1.0), "grounded": score > 0.6}

    def _check_temporal_expressions(self, answer: str) -> list[str]:
        """시의성 표현 검증 (temporal_expression_check)."""
        violations = []
        # 패턴: (최근|현재|올해|전일|전월|지난달)
        if re.search(r"(최근|현재|올해|전일|전월|지난달)", answer) and (
            "(이미지 기준)" not in answer and "(보고서 기준)" not in answer
        ):
            violations.append(
                "시의성 표현 사용 시 '(이미지 기준)' 또는 '(보고서 기준)' 표기 필수",
            )
        return violations

    def _check_repetition(self, answer: str, max_repeat: int = 2) -> list[str]:
        """반복 표현 검증 (repetition_check) - 형태소 분석 기반."""
        violations = []

        try:
            kiwipiepy: Any = importlib.import_module("kiwipiepy")
            Kiwi = kiwipiepy.Kiwi

            # Kiwi 인스턴스 생성 (첫 호출 시 모델 로딩)
            kiwi = Kiwi()

            # 형태소 분석
            result = kiwi.tokenize(answer)

            # 명사(N*), 동사(V*) 어근만 추출
            morphs = [
                token.form
                for token in result
                if token.tag.startswith("N") or token.tag.startswith("V")
            ]

            # 한국어 stopwords
            stopwords = {
                "것",
                "수",
                "때",
                "등",
                "이",
                "그",
                "저",
                "및",
                "또는",
                "중",
                "안",
                "밖",
            }

            # 빈도 계산
            morph_counts: dict[str, int] = {}
            for morph in morphs:
                if morph not in stopwords and len(morph) > 1 and not morph.isdigit():
                    morph_counts[morph] = morph_counts.get(morph, 0) + 1

            # 반복 빈도가 높은 형태소만 보고 (상위 10개)
            top_morphs = sorted(morph_counts.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
            for morph, count in top_morphs:
                if count > max_repeat:
                    violations.append(
                        f"'{morph}' 과도한 반복 ({count}회, 최대 {max_repeat}회)",
                    )

        except ImportError:
            # kiwipiepy가 없으면 기존 방식으로 fallback
            self.logger.warning("kiwipiepy not available, using simple word matching")
            stopwords = {
                "것",
                "등",
                "및",
                "또는",
                "이",
                "그",
                "저",
                "수",
                "때",
                "중",
                "안",
                "밖",
            }

            words = re.findall(r"\b\w{2,}\b", answer)
            word_counts: dict[str, int] = {}
            for word in words:
                if word not in stopwords and not word.isdigit():
                    word_counts[word] = word_counts.get(word, 0) + 1

            top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
            for word, count in top_words:
                if count > max_repeat:
                    violations.append(
                        f"'{word}' 과도한 반복 ({count}회, 최대 {max_repeat}회)",
                    )

        return violations

    def _check_formatting_rules(self, answer: str) -> list[str]:
        """형식 규칙 검증 (formatting_rules)."""
        violations = []

        # 목록형 답변 감지 (숫자 불릿 또는 기호 불릿)
        has_numbered_bullets = bool(re.search(r"^\d+\.\s", answer, re.MULTILINE))
        has_symbol_bullets = bool(re.search(r"^[-*•]\s", answer, re.MULTILINE))

        if has_numbered_bullets or has_symbol_bullets:
            # 1. 목록형 답변에서 문단 구분 검사 (불릿 사이에 빈 줄)
            if has_numbered_bullets and re.search(
                r"(^\d+\.\s.+\n\s*\n+\d+\.\s)",
                answer,
                re.MULTILINE,
            ):
                violations.append(
                    "목록형 답변은 문단 구분하지 않음 (불릿 사이 빈 줄 제거 필요)",
                )
            if has_symbol_bullets and re.search(
                r"(^[-*•]\s.+\n\s*\n+[-*•]\s)",
                answer,
                re.MULTILINE,
            ):
                violations.append(
                    "목록형 답변은 문단 구분하지 않음 (불릿 사이 빈 줄 제거 필요)",
                )

            # 2. 불릿 간격 일관성 (- vs * 혼용)
            if has_symbol_bullets:
                dash_bullets = re.findall(r"^-\s", answer, re.MULTILINE)
                star_bullets = re.findall(r"^\*\s", answer, re.MULTILINE)
                if dash_bullets and star_bullets:
                    violations.append("불릿 표시 일관성 필요 (- 또는 * 중 하나만 사용)")

        return violations

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
                max_rep = c.get("max_repetition", 2)
                violations.extend(self._check_repetition(answer, max_rep))

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
