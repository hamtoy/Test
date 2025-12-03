"""Helper services extracted from GeminiAgent to reduce core responsibilities."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import ValidationError

from src.config.exceptions import APIRateLimitError, ValidationFailedError
from src.core.models import EvaluationResultSchema, QueryResult
from src.infra.utils import clean_markdown_code_block, safe_json_parse

if TYPE_CHECKING:
    import google.generativeai.caching as caching

    from src.agent import GeminiAgent
    from src.qa.rag_system import QAKnowledgeGraph


class QueryGeneratorService:
    """Encapsulates query generation steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    async def generate_query(
        self,
        ocr_text: str,
        user_intent: Optional[str],
        cached_content: Optional["caching.CachedContent"],
        template_name: Optional[str],
        query_type: str,
        kg: Optional["QAKnowledgeGraph"],
        constraints: Optional[List[Dict[str, Any]]],
    ) -> List[str]:
        agent = self.agent
        agent._api_call_counter.add(1, {"operation": "generate_query"})  # noqa: SLF001
        user_template_name = template_name or "user/query_gen.j2"
        user_template = agent.jinja_env.get_template(user_template_name)
        user_prompt = user_template.render(ocr_text=ocr_text, user_intent=user_intent)

        schema_json = json.dumps(
            QueryResult.model_json_schema(), indent=2, ensure_ascii=False
        )

        constraint_list = constraints if constraints is not None else []
        kg_obj = kg
        try:
            if not constraint_list and kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            if not constraint_list and kg_obj is not None:
                all_constraints = kg_obj.get_constraints_for_query_type(query_type)
                constraint_list = [
                    c for c in all_constraints if c.get("category") in ["query", "both"]
                ]
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Neo4j 제약사항 조회 실패: %s", e)

        if constraint_list:
            constraint_list.sort(key=lambda x: x.get("priority", 0), reverse=True)

        rules: List[str] = []
        try:
            if kg_obj is not None:
                rules = kg_obj.find_relevant_rules(ocr_text[:500], k=10)
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Neo4j 규칙 조회 실패: %s", e)

        formatting_rules = ""
        try:
            if kg_obj:
                formatting_rules = kg_obj.get_formatting_rules("query_gen")
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Formatting rules 조회 실패: %s", e)

        guide_rules: List[Dict[str, str]] = []
        common_mistakes: List[Dict[str, str]] = []
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
                    context_stage="query",
                )
                guide_rules = template_context.get("guide_rules", []) or []
                common_mistakes = template_context.get("common_mistakes", []) or []
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", e)

        system_template_name = "system/query_gen.j2"
        try:
            system_template = agent.jinja_env.get_template(system_template_name)
            system_prompt = system_template.render(
                response_schema=schema_json,
                rules=rules,
                constraints=constraint_list,
                formatting_rules=formatting_rules,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
            )
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("템플릿 렌더링 실패: %s", e)
            system_prompt = agent.jinja_env.get_template(system_template_name).render(
                response_schema=schema_json,
                formatting_rules=formatting_rules,
                constraints=constraint_list,
            )

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt, response_schema=QueryResult, cached_content=cached_content
        )

        agent.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await agent.retry_handler.call(model, user_prompt)
        except Exception as e:
            if agent._is_rate_limit_error(e):  # noqa: SLF001
                raise APIRateLimitError(
                    "Rate limit exceeded during query generation: %s" % e
                ) from e
            raise

        cleaned_response = clean_markdown_code_block(response_text)
        if not cleaned_response or not cleaned_response.strip():
            agent.logger.error("Query Generation: Empty response received")
            return []

        try:
            result = QueryResult.model_validate_json(cleaned_response)
            return result.queries if result.queries else []
        except ValidationError as e:
            agent.logger.error(
                "Query Validation Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            return []
        except json.JSONDecodeError as e:
            agent.logger.error(
                "Query JSON Parse Failed: %s. Response: %s...",
                e,
                cleaned_response[:200],
            )
            return []
        except (TypeError, KeyError, AttributeError) as e:
            agent.logger.error("Unexpected error in query parsing: %s", e)
            return []


class ResponseEvaluatorService:
    """Encapsulates response evaluation steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    async def evaluate_responses(
        self,
        ocr_text: str,
        query: str,
        candidates: Dict[str, str],
        cached_content: Optional["caching.CachedContent"],
        query_type: str,
        kg: Optional["QAKnowledgeGraph"],
    ) -> Optional["EvaluationResultSchema"]:
        if not query:
            return None
        agent = self.agent
        agent._api_call_counter.add(1, {"operation": "evaluate"})  # noqa: SLF001

        input_data = {
            "ocr_ground_truth": ocr_text,
            "target_query": query,
            "candidates": candidates,
        }

        rules: List[str] = []
        constraints: List[str] = []
        kg_obj = kg
        try:
            if kg_obj is None:
                from src.qa.rag_system import QAKnowledgeGraph

                kg_obj = QAKnowledgeGraph()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            for c in constraint_list:
                desc = c.get("description")
                if desc:
                    constraints.append(desc)
            rules = kg_obj.find_relevant_rules(ocr_text[:500], k=10)
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Neo4j 규칙 조회 실패: %s", e)

        formatting_rules = ""
        try:
            if kg_obj:
                formatting_rules = kg_obj.get_formatting_rules("eval")
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Formatting rules 조회 실패: %s", e)

        try:
            system_template = agent.jinja_env.get_template("system/qa/compare_eval.j2")
            system_prompt = system_template.render(
                rules=rules,
                constraints=constraints,
                formatting_rules=formatting_rules,
            )
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("템플릿 렌더링 실패: %s", e)
            system_prompt = agent.jinja_env.get_template("system/eval.j2").render()

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt,
            response_schema=EvaluationResultSchema,
            cached_content=cached_content,
        )

        agent.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await agent.retry_handler.call(
                model, json.dumps(input_data, ensure_ascii=False)
            )
        except Exception as e:
            if agent._is_rate_limit_error(e):  # noqa: SLF001
                raise APIRateLimitError(
                    "Rate limit exceeded during evaluation: %s" % e
                ) from e
            raise

        try:
            cleaned_response = clean_markdown_code_block(response_text)
            if not cleaned_response or not cleaned_response.strip():
                agent.logger.error("Evaluation: Empty response received")
                return None
            result = EvaluationResultSchema.model_validate_json(cleaned_response)
            return result
        except ValidationError as e:
            agent.logger.error(
                "Evaluation Validation Failed: %s. Response: %s...",
                e,
                response_text[:200],
            )
            raise ValidationFailedError("Evaluation validation failed: %s" % e) from e
        except json.JSONDecodeError as e:
            agent.logger.error(
                "Evaluation JSON Parse Failed: %s. Response: %s...",
                e,
                response_text[:200],
            )
            raise ValidationFailedError("Evaluation JSON parsing failed: %s" % e) from e


class RewriterService:
    """Encapsulates answer rewrite steps."""

    def __init__(self, agent: GeminiAgent) -> None:
        self.agent = agent

    async def rewrite_best_answer(
        self,
        user_query: str,
        selected_answer: str,
        edit_request: Optional[str],
        formatting_rules: Optional[str],
        cached_content: Optional["caching.CachedContent"],
        query_type: str,
    ) -> str:
        agent = self.agent
        constraint_list: List[Dict[str, Any]] = []
        rules: List[str] = []
        kg_obj: Optional["QAKnowledgeGraph"] = None

        try:
            from src.qa.rag_system import QAKnowledgeGraph

            kg_obj = QAKnowledgeGraph()
            constraint_list = kg_obj.get_constraints_for_query_type(query_type)
            rules = kg_obj.find_relevant_rules(user_query[:500], k=10)
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("Neo4j 조회 실패 (선택사항): %s", e)

        if constraint_list:
            constraint_list.sort(key=lambda x: x.get("priority", 0), reverse=True)

        guide_rules: List[Dict[str, str]] = []
        common_mistakes: List[Dict[str, str]] = []
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
                    context_stage="rewrite",
                )
                guide_rules = template_context.get("guide_rules", []) or []
                common_mistakes = template_context.get("common_mistakes", []) or []
        except Exception as e:  # noqa: BLE001
            agent.logger.debug("CSV 가이드 조회 실패 (선택사항): %s", e)

        if formatting_rules is None and kg_obj:
            try:
                formatting_rules = kg_obj.get_formatting_rules("rewrite")
            except Exception as e:  # noqa: BLE001
                agent.logger.debug("Formatting rules 조회 실패: %s", e)

        length_constraint = getattr(agent.config, "target_length", None)

        payload = json.dumps(
            {
                "query": user_query,
                "selected_answer": selected_answer,
                "user_edit_request": edit_request,
            },
            ensure_ascii=False,
        )

        try:
            system_template = agent.jinja_env.get_template("system/qa/rewrite.j2")
            system_prompt = system_template.render(
                rules=rules,
                constraints=constraint_list,
                guide_rules=guide_rules,
                common_mistakes=common_mistakes,
                has_table_chart=False,
                formatting_rules=formatting_rules,
                length_constraint=length_constraint,
            )
        except Exception as e:  # noqa: BLE001
            agent.logger.warning("동적 템플릿 실패, 기본 사용: %s", e)
            system_prompt = agent.jinja_env.get_template("system/rewrite.j2").render(
                formatting_rules=formatting_rules,
                constraints=constraint_list,
                length_constraint=length_constraint,
            )

        model = agent._create_generative_model(  # noqa: SLF001
            system_prompt, cached_content=cached_content
        )

        agent.context_manager.track_cache_usage(cached_content is not None)

        try:
            response_text = await agent.retry_handler.call(model, payload)
        except Exception as e:
            if agent._is_rate_limit_error(e):  # noqa: SLF001
                raise APIRateLimitError(
                    "Rate limit exceeded during rewrite: %s" % e
                ) from e
            raise

        unwrapped = safe_json_parse(response_text, "rewritten_answer")

        if isinstance(unwrapped, str):
            return unwrapped

        return response_text if response_text else ""
