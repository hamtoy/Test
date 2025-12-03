from __future__ import annotations

import logging
from contextlib import suppress
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    Template,
    TemplateNotFound,
)
from neo4j import GraphDatabase

from src.config.utils import require_env

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "templates"


class DynamicTemplateGenerator:
    """그래프에 저장된 Rule/Constraint/Example을 템플릿 컨텍스트에 주입해
    질의 유형별 프롬프트를 렌더링하고, 세션 검증 체크리스트를 생성합니다.
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize the dynamic template generator.

        Args:
            neo4j_uri: Neo4j database URI.
            neo4j_user: Neo4j username.
            neo4j_password: Neo4j password.
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.logger = logging.getLogger(__name__)
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATE_DIR)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=True,
        )

    def close(self) -> None:
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def _run(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Run a Cypher query and return list of records."""
        params = params or {}
        with self.driver.session() as session:
            return list(session.run(cypher, **params))

    def generate_prompt_for_query_type(
        self, query_type: str, context: Dict[str, Any]
    ) -> str:
        """질의 유형에 맞는 시스템 템플릿을 그래프 지식과 합쳐 렌더링."""
        cypher = """
        MATCH (qt:QueryType {name: $type})
        OPTIONAL MATCH (qt)<-[:APPLIES_TO]-(r:Rule)
        OPTIONAL MATCH (r)-[:ENFORCES]->(c:Constraint)
        OPTIONAL MATCH (bp:BestPractice)-[:APPLIES_TO]->(qt)
        OPTIONAL MATCH (e:Example)
        WITH qt,
             collect(DISTINCT r.text) AS rules,
             collect(DISTINCT c.description) AS constraints,
             collect(DISTINCT bp.text) AS best_practices,
             collect(DISTINCT {text: e.text, type: e.type}) AS examples
        RETURN qt.korean AS type_name, rules, constraints, best_practices, examples
        """
        records = self._run(cypher, {"type": query_type})
        if not records:
            raise ValueError(f"QueryType '{query_type}'을(를) 찾을 수 없습니다.")
        data = records[0]

        # CSV 가이드 데이터 가져오기
        guide_rules: list[dict[str, str]] = []
        common_mistakes: list[dict[str, str]] = []
        try:
            from src.qa.template_rules import get_all_template_context

            template_context = get_all_template_context(
                query_type=query_type,
                neo4j_uri=self.neo4j_uri,
                neo4j_user=self.neo4j_user,
                neo4j_password=self.neo4j_password,
                include_mistakes=True,
            )
            guide_rules = template_context.get("guide_rules", []) or []
            common_mistakes = template_context.get("common_mistakes", []) or []
        except Exception as e:
            self.logger.warning("CSV 가이드 데이터 조회 실패: %s", e)

        template_map = {
            "explanation": "system/qa/explanation.j2",
            "global_explanation": "system/qa/global.j2",
            "summary": "system/qa/summary.j2",
            "reasoning": "system/qa/reasoning.j2",
            "target": "user/qa/target.j2",
            "target_short": "user/qa/target.j2",
            "target_long": "user/qa/target.j2",
            "factual": "user/qa/target.j2",
            "general": "system/qa/explanation.j2",
        }
        template_name = template_map.get(query_type, "system/base.j2")
        fallback = "system/base.j2"
        try:
            template: Template = self.jinja_env.get_template(template_name)
        except TemplateNotFound as exc:
            self.logger.warning(
                "Template %s not found (%s), using fallback", template_name, exc
            )
            template = self.jinja_env.get_template(fallback)

        full_context = {
            **context,
            "query_type_korean": data["type_name"],
            "rules": data["rules"],
            "constraints": data["constraints"],
            "best_practices": data["best_practices"],
            "examples": data["examples"],
            "guide_rules": guide_rules,
            "common_mistakes": common_mistakes,
            "calc_allowed": context.get(
                "calc_allowed", context.get("used_calc_query_count", 0) < 1
            ),
        }
        return str(template.render(**full_context))

    def generate_validation_checklist(
        self, session: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """세션에 포함된 QueryType에 대해 그래프에서 제약을 수집해 체크리스트 생성."""
        query_types = {t.get("type") for t in session.get("turns", []) if t.get("type")}
        checklist: List[Dict[str, Any]] = []
        cypher = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (r:Rule)-[:APPLIES_TO]->(qt)
        OPTIONAL MATCH (r)-[:ENFORCES]->(c:Constraint)
        OPTIONAL MATCH (t:Template)-[:ENFORCES]->(c2:Constraint)
        WITH qt, collect(DISTINCT c) + collect(DISTINCT c2) AS cons
        UNWIND cons AS c
        RETURN DISTINCT c.description AS item, c.type AS category
        """
        for qt in query_types:
            checklist.extend(
                {
                    "item": record["item"],
                    "category": record["category"],
                    "query_type": qt,
                }
                for record in self._run(cypher, {"qt": qt})
            )
        return checklist


if __name__ == "__main__":
    generator: Optional[DynamicTemplateGenerator] = None
    try:
        generator = DynamicTemplateGenerator(
            neo4j_uri=require_env("NEO4J_URI"),
            neo4j_user=require_env("NEO4J_USER"),
            neo4j_password=require_env("NEO4J_PASSWORD"),
        )

        context = {
            "image_path": "sample.png",
            "has_table_chart": True,
            "session_turns": 4,
            "language_hint": "ko",
            "text_density": "high",
        }

        prompt = generator.generate_prompt_for_query_type("explanation", context)
        print("🎯 생성된 프롬프트 (앞부분):")
        print(prompt[:500], "...\n")

        test_session = {
            "turns": [
                {"type": "explanation"},
                {"type": "reasoning"},
                {"type": "target"},
                {"type": "target"},
            ]
        }
        checklist = generator.generate_validation_checklist(test_session)
        print("📝 검증 체크리스트:")
        for item in checklist:
            print(f"  [{item['query_type']}] {item['item']}")

    except Exception as e:
        print(f"❌ 실행 실패: {e}")
    finally:
        if generator is not None:
            with suppress(Exception):
                generator.close()
