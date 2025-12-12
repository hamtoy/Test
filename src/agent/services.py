"""Helper services extracted from GeminiAgent to reduce core responsibilities."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from src.config.exceptions import APIRateLimitError, ValidationFailedError
from src.core.models import (
    EvaluationResultSchema,
    QueryResult,
    StructuredAnswerSchema,
)
from src.infra.utils import clean_markdown_code_block, safe_json_parse

if TYPE_CHECKING:
    from google.generativeai import caching

    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph


_FORMATTING_RULES_FETCH_FAILED = "Formatting rules 조회 실패: %s"


async def _call_model_with_rate_limit_handling(
    agent: GeminiAgent,
    model: Any,
    payload: str,
    *,
    operation: str,
) -> str:
    try:
        return await agent.retry_handler.call(model, payload)
    except Exception as exc:  # noqa: BLE001
        if agent._is_rate_limit_error(exc):  # noqa: SLF001
            raise APIRateLimitError(
                f"Rate limit exceeded during {operation}: {exc}",
            ) from exc
        raise


def _load_guide_context_shared(
    agent: GeminiAgent,
    query_type: str,
    context_stage: str,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load guide rules and common mistakes from CSV (shared helper)."""
    guide_rules: list[dict[str, str]] = []
    common_mistakes: list[dict[str, str]] = []
    try:
        from src.qa.template_rules import (
            get_all_template_context,
            get_neo4j_config,
        )

        neo4j_config = get_neo4j_config()
        if neo4j_config.get("neo4j_password"):
            template_context = get_all_template_context(
                query_type=query_type,
                neo4j_uri=neo4j_config["neo4j_uri"],
                neo4j_user=neo4j_config["neo4j_user"],
                neo4j_password=neo4j_config["neo4j_password"],
                include_mistakes=True,
                context_stage=context_stage,
            )
            guide_rules = template_context.get("guide_rules", []) or []
            common_mistakes = template_context.get("common_mistakes", []) or []
    except Exception as exc:  # noqa: BLE001
        agent.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", exc)
    return guide_rules, common_mistakes


class QueryGeneratorService:
    """Encapsulates query generation steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the query generator service."""
        self.agent = agent

    def _build_user_prompt(
        self,
        ocr_text: str,
        user_intent: str | None,
        template_name: str | None,
    ) -> str:
        agent = self.agent
        user_template_name = template_name or "user/query_gen.j2"
        user_template = agent.jinja_env.get_template(user_template_name)
        return user_template.render(ocr_text=ocr_text, user_intent=user_intent)

    def _schema_json(self) -> str:
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
        agent = self.agent
        constraint_list = constraints if constraints is not None else []
        kg_obj = kg
        try:
            if not constraint_list and kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
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
    ) -> list[str]:
        agent = self.agent
        if kg_obj is None:
            return []
        try:
            return kg_obj.find_relevant_rules(ocr_text[:500], k=10)
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 규칙 조회 실패: %s", exc)
            return []

    def _load_formatting_rules(self, kg_obj: QAKnowledgeGraph | None) -> str:
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
        return _load_guide_context_shared(self.agent, query_type, "query")

    def _render_system_prompt(
        self,
        schema_json: str,
        rules: list[str],
        constraints: list[dict[str, Any]],
        formatting_rules: str,
        guide_rules: list[dict[str, str]],
        common_mistakes: list[dict[str, str]],
    ) -> str:
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
            agent.logger.debug("Raw response (truncated): %s", response_text[:500])

    def _parse_queries(
        self,
        cleaned_response: str,
        query_type: str,
    ) -> list[str]:
        agent = self.agent
        try:
            result = QueryResult.model_validate_json(cleaned_response)
            if not result.queries:
                agent.logger.warning(
                    "Query Generation: Empty queries list returned | "
                    "query_type=%s | response=%s...",
                    query_type,
                    cleaned_response[:200],
                )
            return result.queries if result.queries else []
        except ValidationError as exc:
            agent.logger.error(
                "Query Validation Failed | query_type=%s | error=%s | response=%s...",
                query_type,
                exc,
                cleaned_response[:200],
            )
            return []
        except json.JSONDecodeError as exc:
            agent.logger.error(
                "Query JSON Parse Failed | query_type=%s | error=%s | response=%s...",
                query_type,
                exc,
                cleaned_response[:200],
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
        cached_content: caching.CachedContent | None,
        template_name: str | None,
        query_type: str,
        kg: QAKnowledgeGraph | None,
        constraints: list[dict[str, Any]] | None,
    ) -> list[str]:
        """Generate candidate queries from OCR text and intent."""
        agent = self.agent
        agent._api_call_counter.add(1, {"operation": "generate_query"})  # noqa: SLF001
        user_prompt = self._build_user_prompt(ocr_text, user_intent, template_name)
        schema_json = self._schema_json()
        constraint_list, kg_obj = self._load_constraints(
            query_type,
            constraints,
            kg,
        )
        rules = self._load_rules(kg_obj, ocr_text)
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

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=QueryResult,
            cached_content=cached_content,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)

        response_text = await _call_model_with_rate_limit_handling(
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


class ResponseEvaluatorService:
    """Encapsulates response evaluation steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the response evaluator service."""
        self.agent = agent

    def _load_eval_context(
        self,
        ocr_text: str,
        query_type: str,
        kg: QAKnowledgeGraph | None,
    ) -> tuple[list[str], list[str], str]:
        agent = self.agent
        rules: list[str] = []
        constraints: list[str] = []
        kg_obj = kg
        try:
            if kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            constraints = [
                desc for c in constraint_list if (desc := c.get("description"))
            ]
            rules = kg_obj.find_relevant_rules(ocr_text[:500], k=10)
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
                response_text[:200],
            )
            raise ValidationFailedError(
                "Evaluation validation failed: %s" % exc,
            ) from exc
        except json.JSONDecodeError as exc:
            agent.logger.error(
                "Evaluation JSON Parse Failed: %s. Response: %s...",
                exc,
                response_text[:200],
            )
            raise ValidationFailedError(
                "Evaluation JSON parsing failed: %s" % exc,
            ) from exc

    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: dict[str, str],
        cached_content: caching.CachedContent | None,
        query_type: str,
        kg: QAKnowledgeGraph | None,
    ) -> EvaluationResultSchema | None:
        """Evaluate candidate answers and return the best choice metadata."""
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
        response_text = await _call_model_with_rate_limit_handling(
            agent,
            model,
            payload,
            operation="evaluation",
        )
        return self._parse_evaluation(response_text)


class RewriterService:
    """Encapsulates answer rewrite steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        """Initialize the rewrite service."""
        self.agent = agent

    def _load_kg_context(
        self,
        query_type: str,
        user_query: str,
    ) -> tuple[list[dict[str, Any]], list[str], QAKnowledgeGraph | None]:
        agent = self.agent
        constraint_list: list[dict[str, Any]] = []
        rules: list[str] = []
        kg_obj: QAKnowledgeGraph | None = None
        try:
            from src.qa.rag_system import QAKnowledgeGraph

            kg_obj = QAKnowledgeGraph()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            rules = kg_obj.find_relevant_rules(user_query[:500], k=10)
        except Exception as exc:  # noqa: BLE001
            agent.logger.debug("Neo4j 조회 실패 (선택사항): %s", exc)
        return constraint_list, rules, kg_obj

    def _sanitize_constraints(
        self,
        constraints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
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
        return _load_guide_context_shared(self.agent, query_type, "rewrite")

    def _resolve_formatting_rules(
        self,
        formatting_rules: str | None,
        kg_obj: QAKnowledgeGraph | None,
    ) -> str | None:
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
        """응답 텍스트를 언래핑. JSON 모드면 구조화된 필드 추출."""
        # JSON 모드 응답 처리 (설명/추론 타입)
        if query_type in {"explanation", "reasoning", "global_explanation"}:
            try:
                import json

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
        """Rewrite a selected answer using constraints and formatting rules."""
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

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=response_schema,
            cached_content=cached_content,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)
        response_text = await _call_model_with_rate_limit_handling(
            agent,
            model,
            payload,
            operation="rewrite",
        )
        return self._unwrap_response(response_text, query_type)
