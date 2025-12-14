"""Lcel Chain module."""
from __future__ import annotations

# mypy: ignore-errors
import logging
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import (
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

from src.llm.gemini import GeminiModelClient
from src.qa.rag_system import QAKnowledgeGraph

logger = logging.getLogger(__name__)


class LCELOptimizedChain:
    """LCEL 기반 병렬 조회 + Gemini 생성을 수행하는 경량 체인."""

    def __init__(
        self,
        kg: QAKnowledgeGraph | None = None,
        llm: GeminiModelClient | None = None,
    ):
        """Initialize the LCEL optimized chain.

        Args:
            kg: Optional QAKnowledgeGraph instance.
            llm: Optional Gemini model client.
        """
        self.kg = kg or QAKnowledgeGraph()
        self.llm = llm or GeminiModelClient()

        self.prompt_template = PromptTemplate(
            input_variables=["rules", "examples", "constraints", "original_context"],
            template=(
                "다음 정보를 모두 반영하여 한국어로 답변을 생성하세요.\n\n"
                "[Rules]\n{rules}\n\n"
                "[Constraints]\n{constraints}\n\n"
                "[Examples]\n{examples}\n\n"
                "[Context]\n{original_context}\n\n"
                "표/그래프 참조는 금지된 경우 제외하고, 고유명사/숫자는 보존하세요."
            ),
        )

        self.chain = (
            RunnableParallel(
                {
                    "rules": RunnableLambda(self._get_rules),
                    "examples": RunnableLambda(self._get_examples),
                    "constraints": RunnableLambda(self._get_constraints),
                    "context": RunnablePassthrough(),
                },
            )
            | RunnableLambda(self._merge_context)
            | RunnableLambda(self._format_prompt)
            | RunnableLambda(self._call_llm)
            | StrOutputParser()
        )

    def _get_rules(self, input_dict: dict[str, Any]) -> list[str]:
        """QueryType별 Rule 텍스트 조회."""
        qt = input_dict.get("query_type", "explanation")
        try:
            graph = getattr(self.kg, "_graph", None)
            if graph is None:
                return []
            with graph.session() as session:
                res = session.run(
                    """
                    MATCH (r:Rule)-[:APPLIES_TO]->(q:QueryType {name: $qt})
                    RETURN r.text AS text
                    """,
                    qt=qt,
                )
                return [r["text"] for r in res]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rule fetch failed: %s", exc)
            return []

    def _get_examples(self, input_dict: dict[str, Any]) -> list[str]:
        """예시 샘플 조회."""
        try:
            rows = self.kg.get_examples(limit=3)
            return [r["text"] for r in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Example fetch failed: %s", exc)
            return []

    def _get_constraints(self, input_dict: dict[str, Any]) -> list[str]:
        """제약 조건 텍스트 조회."""
        qt = input_dict.get("query_type", "explanation")
        try:
            cons = self.kg.get_constraints_for_query_type(qt)
            return [c.get("description", "") for c in cons]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Constraint fetch failed: %s", exc)
            return []

    def _merge_context(self, parallel_output: dict[str, Any]) -> dict[str, Any]:
        """병렬 결과 병합."""
        return {
            "rules": parallel_output.get("rules", []),
            "examples": parallel_output.get("examples", []),
            "constraints": parallel_output.get("constraints", []),
            "original_context": parallel_output.get("context", {}),
        }

    def _format_prompt(self, merged: dict[str, Any]) -> str:
        return self.prompt_template.format(
            rules="\n".join(f"- {r}" for r in merged["rules"]) or "(규칙 없음)",
            examples="\n".join(f"- {e}" for e in merged["examples"]) or "(예시 없음)",
            constraints="\n".join(f"- {c}" for c in merged["constraints"])
            or "(제약 없음)",
            original_context=merged["original_context"],
        )

    def _call_llm(self, prompt: str) -> str:
        return self.llm.generate(prompt, role="lcel")

    def invoke(self, input_dict: dict[str, Any]) -> str:
        """체인을 실행해 최종 답변을 반환."""
        return self.chain.invoke(input_dict)
