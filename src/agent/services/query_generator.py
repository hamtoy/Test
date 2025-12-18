"""Query generation service module.

Encapsulates all query generation logic extracted from GeminiAgent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from src.config.constants import LOG_TRUNCATE_LENGTH, RULE_LOOKUP_OCR_SNIPPET_LENGTH
from src.core.models import QueryResult
from src.infra.utils import clean_markdown_code_block

from ._utils import (
    _FORMATTING_RULES_FETCH_FAILED,
    call_model_with_rate_limit_handling,
    load_guide_context_shared,
)

if TYPE_CHECKING:
    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph


class QueryGeneratorService:
    """Encapsulates query generation steps.

    This service handles the complete flow of generating strategic queries
    from OCR text and user intent, including:
    - Loading constraints and rules from Neo4j
    - Rendering system prompts with Jinja2
    - Calling the LLM and parsing responses
    """

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the query generator service.

        Args:
            agent: The GeminiAgent instance to use for API calls.
        """
        self.agent = agent

    def _build_user_prompt(
        self,
        ocr_text: str,
        user_intent: str | None,
        template_name: str | None,
    ) -> str:
        """Build the user prompt from OCR text and intent."""
        agent = self.agent
        user_template_name = template_name or "user/query_gen.j2"
        user_template = agent.jinja_env.get_template(user_template_name)
        return user_template.render(ocr_text=ocr_text, user_intent=user_intent)

    def _schema_json(self) -> str:
        """Generate JSON schema for query result."""
        return json.dumps(
            QueryResult.model_json_schema(),
            indent=2,
            ensure_ascii=False,
        )

    def _load_constraints(
        self,
        query_type: str,
        constraints: list[dict[str, Any]] | None,
        kg: QAKnowledgeGraph | None,
    ) -> tuple[list[dict[str, Any]], QAKnowledgeGraph | None]:
        """Load constraints from Neo4j knowledge graph."""
        agent = self.agent
        constraint_list = constraints if constraints is not None else []
        kg_obj = kg
        try:
            if not constraint_list and kg_obj is None:
                from src.qa.kg_provider import get_or_create_kg

                kg_obj = get_or_create_kg()
            if not constraint_list and kg_obj is not None:
                all_constraints = kg_obj.get_constraints_for_query_type(query_type)
                constraint_list = [
                    c for c in all_constraints if c.get("category") in {"query", "both"}
                ]
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 제약사항 조회 실패: %s", exc)

        if constraint_list:
            constraint_list.sort(
                key=lambda x: (x.get("priority") or 0)
                if isinstance(x.get("priority"), (int, float))
                else 0,
                reverse=True,
            )
        return constraint_list, kg_obj

    def _load_rules(
        self,
        kg_obj: QAKnowledgeGraph | None,
        ocr_text: str,
        query_type: str | None = None,
    ) -> list[str]:
        """Load relevant rules from Neo4j."""
        agent = self.agent
        if kg_obj is None:
            return []
        try:
            return kg_obj.find_relevant_rules(
                ocr_text[:RULE_LOOKUP_OCR_SNIPPET_LENGTH],
                k=10,
                query_type=query_type,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 규칙 조회 실패: %s", exc)
            return []

    def _load_formatting_rules(self, kg_obj: QAKnowledgeGraph | None) -> str:
        """Load formatting rules from Neo4j."""
        agent = self.agent
        if not kg_obj:
            return ""
        try:
            return kg_obj.get_formatting_rules("query_gen")
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug(_FORMATTING_RULES_FETCH_FAILED, exc)
            return ""

    def _load_guide_context(
        self,
        query_type: str,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Load guide rules and common mistakes."""
        return load_guide_context_shared(self.agent, query_type, "query")

    def _render_system_prompt(
        self,
        schema_json: str,
        rules: list[str],
        constraints: list[dict[str, Any]],
        formatting_rules: str,
        guide_rules: list[dict[str, str]],
        common_mistakes: list[dict[str, str]],
    ) -> str:
        """Render the system prompt using Jinja2 template."""
        agent = self.agent
        system_template_name = "system/query_gen.j2"
        try:
            system_template = agent.jinja_env.get_template(system_template_name)
            return system_template.render(
                response_schema=schema_json,
                rules=rules,
                constraints=constraints,
                formatting_rules=formatting_rules,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("템플릿 렌더링 실패: %s", exc)
            return agent.jinja_env.get_template(system_template_name).render(
                response_schema=schema_json,
                formatting_rules=formatting_rules,
                constraints=constraints,
            )

    def _log_empty_response(
        self,
        response_text: str,
        query_type: str,
        ocr_text: str,
    ) -> None:
        """Log error when LLM returns empty response."""
        agent = self.agent
        agent.logger.error(
            "Query Generation: Empty response received | "
            "query_type=%s | ocr_length=%d | raw_response_length=%d | "
            "possible_cause=safety_filter_or_rate_limit",
            query_type,
            len(ocr_text),
            len(response_text) if response_text else 0,
        )
        if response_text:
            agent.logger.debug(
                "Raw response (truncated): %s",
                response_text[:RULE_LOOKUP_OCR_SNIPPET_LENGTH],
            )

    def _parse_queries(
        self,
        cleaned_response: str,
        query_type: str,
    ) -> list[str]:
        """Parse LLM response into query list."""
        agent = self.agent
        try:
            result = QueryResult.model_validate_json(cleaned_response)
            if not result.queries:
                agent.logger.warning(
                    "Query Generation: Empty queries list returned | "
                    "query_type=%s | response=%s...",
                    query_type,
                    cleaned_response[:LOG_TRUNCATE_LENGTH],
                )
            return result.queries if result.queries else []
        except ValidationError as exc:
            agent.logger.error(
                "Query Validation Failed | query_type=%s | error=%s | response=%s...",
                query_type,
                exc,
                cleaned_response[:LOG_TRUNCATE_LENGTH],
            )
            return []
        except json.JSONDecodeError as exc:
            agent.logger.error(
                "Query JSON Parse Failed | query_type=%s | error=%s | response=%s...",
                query_type,
                exc,
                cleaned_response[:LOG_TRUNCATE_LENGTH],
            )
            return []
        except (TypeError, KeyError, AttributeError) as exc:
            agent.logger.error(
                "Unexpected error in query parsing | query_type=%s | error=%s",
                query_type,
                exc,
            )
            return []

    async def generate_query(
        self,
        ocr_text: str,
        user_intent: str | None,
        cached_content: Any | None,
        template_name: str | None,
        query_type: str,
        kg: QAKnowledgeGraph | None,
        constraints: list[dict[str, Any]] | None,
    ) -> list[str]:
        """Generate candidate queries from OCR text and intent.

        Args:
            ocr_text: The OCR text to generate queries from.
            user_intent: Optional user intent to guide query generation.
            cached_content: Optional cached content for API optimization.
            template_name: Optional custom template name.
            query_type: Type of query (explanation, reasoning, etc).
            kg: Optional knowledge graph instance.
            constraints: Optional pre-loaded constraints.

        Returns:
            List of generated query strings.
        """
        agent = self.agent
        agent._api_call_counter.add(1, {"operation": "generate_query"})  # noqa: SLF001
        user_prompt = self._build_user_prompt(ocr_text, user_intent, template_name)
        schema_json = self._schema_json()
        constraint_list, kg_obj = self._load_constraints(
            query_type,
            constraints,
            kg,
        )
        rules = self._load_rules(kg_obj, ocr_text, query_type)
        formatting_rules = self._load_formatting_rules(kg_obj)
        guide_rules, common_mistakes = self._load_guide_context(query_type)
        system_prompt = self._render_system_prompt(
            schema_json,
            rules,
            constraint_list,
            formatting_rules,
            guide_rules,
            common_mistakes,
        )

        # Query generation needs more tokens than answer generation
        # (JSON output with multiple queries requires at least 2048 tokens
        # due to schema validation overhead)
        resolved_tokens = agent.config.resolve_max_output_tokens(query_type)
        max_output_tokens = max(resolved_tokens, 2048)
        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=QueryResult,
            cached_content=cached_content,
            max_output_tokens=max_output_tokens,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)

        response_text = await call_model_with_rate_limit_handling(
            agent,
            model,
            user_prompt,
            operation="query generation",
        )

        cleaned_response = clean_markdown_code_block(response_text)
        if not cleaned_response or not cleaned_response.strip():
            self._log_empty_response(response_text, query_type, ocr_text)
            return []

        return self._parse_queries(cleaned_response, query_type)


__all__ = ["QueryGeneratorService"]
