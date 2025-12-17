"""Response evaluation service module.

Encapsulates all response evaluation logic extracted from GeminiAgent.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from src.config.constants import LOG_TRUNCATE_LENGTH, RULE_LOOKUP_OCR_SNIPPET_LENGTH
from src.config.exceptions import ValidationFailedError
from src.core.models import EvaluationResultSchema
from src.infra.utils import clean_markdown_code_block

from ._utils import (
    _FORMATTING_RULES_FETCH_FAILED,
    call_model_with_rate_limit_handling,
)

if TYPE_CHECKING:
    from typing import Any

    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph


class ResponseEvaluatorService:
    """Encapsulates response evaluation steps.

    This service handles the complete flow of evaluating candidate answers,
    including:
    - Loading evaluation context from Neo4j
    - Rendering evaluation prompts
    - Calling the LLM and parsing evaluation results
    """

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the response evaluator service.

        Args:
            agent: The GeminiAgent instance to use for API calls.
        """
        self.agent = agent

    def _load_eval_context(
        self,
        ocr_text: str,
        query_type: str,
        kg: QAKnowledgeGraph | None,
    ) -> tuple[list[str], list[str], str]:
        """Load evaluation context from Neo4j.

        Returns:
            Tuple of (rules, constraints, formatting_rules).
        """
        agent = self.agent
        rules: list[str] = []
        constraints: list[str] = []
        kg_obj = kg
        try:
            if kg_obj is None:
                from src.qa.kg_provider import get_or_create_kg

                kg_obj = get_or_create_kg()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            constraints = [
                desc for c in constraint_list if (desc := c.get("description"))
            ]
            rules = kg_obj.find_relevant_rules(
                ocr_text[:RULE_LOOKUP_OCR_SNIPPET_LENGTH],
                k=10,
                query_type=query_type,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 규칙 조회 실패: %s", exc)

        formatting_rules = ""
        if kg_obj:
            try:
                formatting_rules = kg_obj.get_formatting_rules("eval")
            except Exception as exc:  # noqa: BLE001
                agent.logger.debug(_FORMATTING_RULES_FETCH_FAILED, exc)

        return rules, constraints, formatting_rules

    def _render_system_prompt(
        self,
        rules: list[str],
        constraints: list[str],
        formatting_rules: str,
    ) -> str:
        """Render the evaluation system prompt."""
        agent = self.agent
        try:
            system_template = agent.jinja_env.get_template("system/qa/compare_eval.j2")
            return system_template.render(
                rules=rules,
                constraints=constraints,
                formatting_rules=formatting_rules,
            )
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("템플릿 렌더링 실패: %s", exc)
            return agent.jinja_env.get_template("system/eval.j2").render()

    def _parse_evaluation(
        self,
        response_text: str,
    ) -> EvaluationResultSchema | None:
        """Parse LLM response into evaluation result."""
        agent = self.agent
        cleaned_response = clean_markdown_code_block(response_text)
        if not cleaned_response or not cleaned_response.strip():
            agent.logger.error("Evaluation: Empty response received")
            return None
        try:
            return EvaluationResultSchema.model_validate_json(cleaned_response)
        except ValidationError as exc:
            agent.logger.error(
                "Evaluation Validation Failed: %s. Response: %s...",
                exc,
                response_text[:LOG_TRUNCATE_LENGTH],
            )
            raise ValidationFailedError(
                "Evaluation validation failed: %s" % exc,
            ) from exc
        except json.JSONDecodeError as exc:
            agent.logger.error(
                "Evaluation JSON Parse Failed: %s. Response: %s...",
                exc,
                response_text[:LOG_TRUNCATE_LENGTH],
            )
            raise ValidationFailedError(
                "Evaluation JSON parsing failed: %s" % exc,
            ) from exc

    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: dict[str, str],
        cached_content: Any | None,
        query_type: str,
        kg: QAKnowledgeGraph | None,
    ) -> EvaluationResultSchema | None:
        """Evaluate candidate answers and return the best choice metadata.

        Args:
            ocr_text: The OCR ground truth text.
            query: The target query to evaluate against.
            candidates: Dictionary of candidate answers (key: id, value: text).
            cached_content: Optional cached content for API optimization.
            query_type: Type of query for context loading.
            kg: Optional knowledge graph instance.

        Returns:
            EvaluationResultSchema with evaluation results, or None if failed.
        """
        if not query:
            return None
        agent = self.agent
        agent._api_call_counter.add(1, {"operation": "evaluate"})  # noqa: SLF001

        input_data = {
            "ocr_ground_truth": ocr_text,
            "target_query": query,
            "candidates": candidates,
        }
        rules, constraints, formatting_rules = self._load_eval_context(
            ocr_text,
            query_type,
            kg,
        )
        system_prompt = self._render_system_prompt(
            rules,
            constraints,
            formatting_rules,
        )

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=EvaluationResultSchema,
            cached_content=cached_content,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)
        payload = json.dumps(input_data, ensure_ascii=False)
        response_text = await call_model_with_rate_limit_handling(
            agent,
            model,
            payload,
            operation="evaluation",
        )
        return self._parse_evaluation(response_text)


__all__ = ["ResponseEvaluatorService"]
