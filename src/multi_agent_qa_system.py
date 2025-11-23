from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.cross_validation import CrossValidationSystem
from src.dynamic_example_selector import DynamicExampleSelector
from src.gemini_model_client import GeminiModelClient
from src.qa_rag_system import QAKnowledgeGraph


class MultiAgentQASystem:
    """
    간소화된 멀티-스텝 품질 파이프라인:
    - 규칙/제약 수집
    - 예시 수집
    - Gemini 생성
    - 사후 검증
    """

    def __init__(self, kg: Optional[QAKnowledgeGraph] = None):
        self.kg = kg or QAKnowledgeGraph()
        self.llm = GeminiModelClient()
        self.example_selector = DynamicExampleSelector(self.kg)
        self.validator = CrossValidationSystem(self.kg)

    def collaborative_generate(
        self, query_type: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        규칙/예시를 모아 Gemini로 생성하고 검증까지 수행합니다.
        """

        rules = self._collect_rules(query_type)
        constraints = self.kg.get_constraints_for_query_type(query_type)
        examples = self.example_selector.select_best_examples(query_type, context, k=3)

        prompt = self._build_prompt(query_type, context, rules, constraints, examples)
        output = self.llm.generate(prompt, role="generator")

        validation = self.validator.cross_validate_qa_pair(
            question=f"{query_type} generation",  # 실제 질문 삽입 가능
            answer=output,
            query_type=query_type,
            image_meta=context,
        )

        return {
            "output": output,
            "validation": validation,
            "metadata": {
                "rules_used": rules,
                "constraints_used": constraints,
                "examples_used": examples,
            },
        }

    def _collect_rules(self, query_type: str) -> List[Dict[str, Any]]:
        """QueryType 관련 Rule/Constraint 텍스트를 수집."""
        rules: List[Dict[str, Any]] = []
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                result = session.run(
                    """
                    MATCH (r:Rule)-[:APPLIES_TO]->(q:QueryType {name: $qt})
                    RETURN r.text AS text
                    """,
                    qt=query_type,
                )
                rules = [{"text": r["text"]} for r in result]
        except Exception:
            rules = []
        return rules

    def _build_prompt(
        self,
        query_type: str,
        context: Dict[str, Any],
        rules: List[Dict[str, Any]],
        constraints: List[Dict[str, Any]],
        examples: List[Dict[str, Any]],
    ) -> str:
        """Gemini에 전달할 통합 프롬프트 생성."""

        rules_text = "\n".join([f"- {r['text']}" for r in rules]) or "(규칙 없음)"
        constraint_text = (
            "\n".join([f"- {c.get('description', '')}" for c in constraints])
            or "(제약 없음)"
        )
        examples_text = (
            "\n".join([f"- {e['example']}" for e in examples]) or "(예시 없음)"
        )

        return f"""당신은 텍스트-이미지 QA 작성자입니다.

[Query Type]
{query_type}

[Context]
{context}

[Rules]
{rules_text}

[Constraints]
{constraint_text}

[Positive Examples]
{examples_text}

위 정보를 모두 준수하여 한국어로 답변을 생성하세요. 표/그래프 참조는 금지된 경우 제외하고, 고유명사/숫자는 보존하세요."""
