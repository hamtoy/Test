"""Answer rewriting service module.

Encapsulates all answer rewriting logic extracted from GeminiAgent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from src.config.constants import RULE_LOOKUP_OCR_SNIPPET_LENGTH
from src.core.models import StructuredAnswerSchema
from src.infra.utils import safe_json_parse

from ._utils import (
    _FORMATTING_RULES_FETCH_FAILED,
    call_model_with_rate_limit_handling,
    load_guide_context_shared,
)

if TYPE_CHECKING:
    from google.generativeai import caching

    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph


class RewriterService:
    """Encapsulates answer rewrite steps.

    This service handles the complete flow of rewriting selected answers,
    including:
    - Loading constraints and rules from Neo4j
    - Rendering rewrite prompts
    - Calling the LLM and processing responses
    """

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the rewrite service.

        Args:
            agent: The GeminiAgent instance to use for API calls.
        """
        self.agent = agent

    def _load_kg_context(
        self,
        query_type: str,
        user_query: str,
    ) -> tuple[list[dict[str, Any]], list[str], QAKnowledgeGraph | None]:
        """Load context from Neo4j knowledge graph."""
        agent = self.agent
        constraint_list: list[dict[str, Any]] = []
        rules: list[str] = []
        kg_obj: QAKnowledgeGraph | None = None
        try:
            from src.qa.kg_provider import get_or_create_kg

            kg_obj = get_or_create_kg()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            rules = kg_obj.find_relevant_rules(
                user_query[:RULE_LOOKUP_OCR_SNIPPET_LENGTH],
                k=10,
                query_type=query_type,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 조회 실패 (선택사항): %s", exc)
        return constraint_list, rules, kg_obj

    def _sanitize_constraints(
        self,
        constraints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Sanitize and sort constraints by priority."""
        if not constraints:
            return []
        sanitized: list[dict[str, Any]] = []
        for c in constraints:
            c_safe = c.copy()
            if not isinstance(c_safe.get("priority"), (int, float)):
                c_safe["priority"] = 0
            sanitized.append(c_safe)
        sanitized.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return sanitized

    def _load_guide_context(
        self,
        query_type: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Load guide rules and common mistakes."""
        return load_guide_context_shared(self.agent, query_type, "rewrite")

    def _resolve_formatting_rules(
        self,
        formatting_rules: str | None,
        kg_obj: QAKnowledgeGraph | None,
    ) -> str | None:
        """Resolve formatting rules from Neo4j if not provided."""
        agent = self.agent
        if formatting_rules is not None or not kg_obj:
            return formatting_rules
        try:
            return kg_obj.get_formatting_rules("rewrite")
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug(_FORMATTING_RULES_FETCH_FAILED, exc)
            return formatting_rules

    def _render_system_prompt(
        self,
        rules: list[str],
        constraints: list[dict[str, Any]],
        guide_rules: list[dict[str, str]],
        common_mistakes: list[dict[str, str]],
        formatting_rules: str | None,
        length_constraint: str | None,
    ) -> str:
        """Render the rewrite system prompt."""
        agent = self.agent
        try:
            system_template = agent.jinja_env.get_template("system/qa/rewrite.j2")
            return system_template.render(
                rules=rules,
                constraints=constraints,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
                has_table_chart=False,
                formatting_rules=formatting_rules,
                length_constraint=length_constraint,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.warning("동적 템플릿 실패, 기본 사용: %s", exc)
            return agent.jinja_env.get_template("system/rewrite.j2").render(
                formatting_rules=formatting_rules,
                constraints=constraints,
                length_constraint=length_constraint,
            )

    def _unwrap_response(self, response_text: str, query_type: str) -> str:
        """Unwrap response text, extracting from JSON if needed.

        Args:
            response_text: Raw response from LLM.
            query_type: Type of query for format detection.

        Returns:
            Unwrapped response text.
        """
        # JSON 모드 응답 처리 (설명/추론 타입)
        if query_type in {"explanation", "reasoning", "global_explanation"}:
            try:
                data = json.loads(response_text)
                if isinstance(data, dict) and "intro" in data:
                    # StructuredAnswerSchema 형식 - JSON 그대로 반환하여
                    # render_structured_answer_if_present()가 처리하도록 함
                    return response_text
            except (json.JSONDecodeError, TypeError):
                pass

        # 기존 로직: rewritten_answer 키 추출
        unwrapped = safe_json_parse(response_text, "rewritten_answer")
        if isinstance(unwrapped, str):
            return unwrapped
        return response_text if response_text else ""

    async def rewrite_best_answer(
        self,
        user_query: str,
        selected_answer: str,
        edit_request: str | None,
        formatting_rules: str | None,
        cached_content: caching.CachedContent | None,
        query_type: str,
    ) -> str:
        """Rewrite a selected answer using constraints and formatting rules.

        Args:
            user_query: The original user query.
            selected_answer: The answer to rewrite.
            edit_request: Optional user edit request.
            formatting_rules: Optional formatting rules.
            cached_content: Optional cached content for API optimization.
            query_type: Type of query for context loading.

        Returns:
            Rewritten answer text.
        """
        agent = self.agent
        constraint_list, rules, kg_obj = self._load_kg_context(
            query_type,
            user_query,
        )
        constraint_list = self._sanitize_constraints(constraint_list)
        guide_rules, common_mistakes = self._load_guide_context(query_type)
        formatting_rules = self._resolve_formatting_rules(formatting_rules, kg_obj)
        length_constraint = getattr(agent.config, "target_length", None)

        payload = json.dumps(
            {
                "query": user_query,
                "selected_answer": selected_answer,
                "user_edit_request": edit_request,
            },
            ensure_ascii=False,
        )
        system_prompt = self._render_system_prompt(
            rules,
            constraint_list,
            guide_rules,
            common_mistakes,
            formatting_rules,
            length_constraint,
        )

        # 설명/추론 타입은 JSON 모드 활성화
        response_schema = None
        if query_type in {"explanation", "reasoning", "global_explanation"}:
            response_schema = StructuredAnswerSchema

        max_output_tokens = agent.config.resolve_max_output_tokens(query_type)
        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=response_schema,
            cached_content=cached_content,
            max_output_tokens=max_output_tokens,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)
        response_text = await call_model_with_rate_limit_handling(
            agent,
            model,
            payload,
            operation="rewrite",
        )
        return self._unwrap_response(response_text, query_type)


__all__ = ["RewriterService"]
