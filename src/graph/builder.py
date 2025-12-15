"""QA 그래프 빌더."""

from __future__ import annotations

import hashlib
import logging
import sys
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from src.config.utils import require_env

from .mappings import CONSTRAINT_KEYWORDS, EXAMPLE_RULE_MAPPINGS, QUERY_TYPE_KEYWORDS
from .schema import (
    BEST_PRACTICES,
    CONSTRAINTS,
    ERROR_PATTERNS,
    QUERY_TYPES,
    TEMPLATES,
)

load_dotenv()


class QAGraphBuilder:
    """Neo4j QA 그래프 구축 클래스."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        """Initialize the QA graph builder.

        Args:
            uri: Neo4j database URI.
            user: Neo4j username.
            password: Neo4j password.
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.logger = logging.getLogger(__name__)

    def close(self) -> None:
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def create_schema_constraints(self) -> None:
        """고유 제약 추가 (존재 시 무시)."""
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT rule_id_unique IF NOT EXISTS FOR (r:Rule) REQUIRE r.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT constraint_id_unique IF NOT EXISTS FOR (c:Constraint) REQUIRE c.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT example_id_unique IF NOT EXISTS FOR (e:Example) REQUIRE e.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT qtype_name_unique IF NOT EXISTS FOR (q:QueryType) REQUIRE q.name IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT template_id_unique IF NOT EXISTS FOR (t:Template) REQUIRE t.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT errorpattern_id_unique IF NOT EXISTS FOR (e:ErrorPattern) REQUIRE e.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT bestpractice_id_unique IF NOT EXISTS FOR (b:BestPractice) REQUIRE b.id IS UNIQUE",
            )
        self.logger.info("스키마 고유 제약 생성/확인 완료")

    def extract_rules_from_notion(self) -> None:
        """Notion 문서에서 규칙 추출 및 그래프화 (UNWIND 배치 처리)."""
        with self.driver.session() as session:
            # 1. Find headings
            headings = self._fetch_rule_headings(session)

            # 2. Collect all rules into batch
            rules_batch: list[dict[str, Any]] = []
            for h in headings:
                current_rules = self._collect_rules_for_heading(session, h)

                for rule_text in current_rules:
                    if not rule_text or len(rule_text) <= 10:
                        continue

                    # 접두사를 포함한 해시 기반 ID로 중복 방지
                    rid = f"rule_{hashlib.sha256(rule_text.encode('utf-8')).hexdigest()[:16]}"
                    rules_batch.append(
                        {
                            "id": rid,
                            "text": rule_text,
                            "section": h["section"],
                        }
                    )

            # 3. Batch insert using UNWIND
            if rules_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MERGE (r:Rule {id: item.id})
                    SET r.text = item.text,
                        r.section = item.section,
                        r.priority = 'high'
                    """,
                    batch=rules_batch,
                )
            print(f"✅ 규칙 {len(rules_batch)}개 추출/병합 완료 (배치 처리)")

    def _fetch_rule_headings(self, session: Any) -> list[dict[str, Any]]:
        headings: list[dict[str, Any]] = session.run(
            """
            MATCH (p:Page)-[:HAS_BLOCK]->(h:Block)
            WHERE h.type = 'heading_1' AND h.content CONTAINS '자주 틀리는'
            RETURN p.id as page_id, h.order as start_order, h.content as section
            """,
        ).data()
        return headings

    def _collect_rules_for_heading(
        self,
        session: Any,
        heading: dict[str, Any],
    ) -> list[str]:
        siblings = session.run(
            """
            MATCH (p:Page {id: $page_id})-[:HAS_BLOCK]->(b:Block)
            WHERE b.order > $start_order
            RETURN b.id as id, b.content as content, b.type as type
            ORDER BY b.order ASC
            """,
            page_id=heading["page_id"],
            start_order=heading["start_order"],
        )
        siblings_list = list(siblings)

        current_rules: list[str] = []
        for sib in siblings_list:
            if sib["type"] == "heading_1":
                break

            if sib["type"] in ["paragraph", "bulleted_list_item", "callout"]:
                current_rules.append(sib["content"])
                continue

            if sib["type"] in ["column_list", "column"]:
                descendants = session.run(
                    """
                    MATCH (b:Block {id: $id})-[:HAS_CHILD*]->(d:Block)
                    WHERE d.type IN ['paragraph', 'bulleted_list_item', 'callout']
                    RETURN d.content as content
                    """,
                    id=sib["id"],
                )
                desc_list: list[dict[str, Any]] = [dict(d) for d in descendants]
                current_rules.extend(
                    d.get("content", "") for d in desc_list if d.get("content")
                )

        return current_rules

    def extract_query_types(self) -> None:
        """질의 유형 정의 추출 (UNWIND 배치 처리)."""
        with self.driver.session() as session:
            # Batch insert using UNWIND
            batch = [
                {
                    "name": qt["name"],
                    "korean": qt["korean"],
                    "limit": qt["limit"],
                    "reconstruction": qt["requires_reconstruction"],
                }
                for qt in QUERY_TYPES
            ]
            session.run(
                """
                UNWIND $batch AS item
                MERGE (q:QueryType {name: item.name})
                SET q.korean = item.korean,
                    q.session_limit = item.limit,
                    q.requires_reconstruction = item.reconstruction
                """,
                batch=batch,
            )
        print(f"✅ 질의 유형 {len(QUERY_TYPES)}개 생성/병합 (배치 처리)")

    def extract_constraints(self) -> None:
        """제약 조건 추출 및 query_type 자동 설정 (UNWIND 배치 처리).

        TEMPLATES의 enforces 관계를 분석하여 각 Constraint가
        어떤 query_type에서 사용되는지 자동으로 매핑합니다.
        """
        # 1. Constraint를 사용하는 Template 매핑 생성
        constraint_to_query_types: dict[str, set[str]] = {}

        for template in TEMPLATES:
            template_name = template["name"]
            query_type = template_name.split("_")[0]

            for constraint_id in template.get("enforces", []):
                if constraint_id not in constraint_to_query_types:
                    constraint_to_query_types[constraint_id] = set()
                constraint_to_query_types[constraint_id].add(query_type)

        # 2. Constraint 노드 배치 생성
        constraint_batch: list[dict[str, Any]] = []
        rel_batch: list[dict[str, str]] = []

        for c in CONSTRAINTS:
            constraint_id = c["id"]
            linked_types = constraint_to_query_types.get(constraint_id, set())

            if not linked_types or len(linked_types) >= 3:
                primary_query_type = None
            else:
                primary_query_type = list(linked_types)[0]

            constraint_batch.append(
                {
                    "id": constraint_id,
                    "desc": c["description"],
                    "type": c["type"],
                    "query_type": primary_query_type,
                }
            )

            rel_batch.extend(
                {"qt": q_type, "cid": constraint_id} for q_type in linked_types
            )

            qt_display = primary_query_type or f"전역({len(linked_types)}개)"
            self.logger.debug(
                f"Constraint '{constraint_id}' -> query_type: {qt_display}, linked: {linked_types}",
            )

        with self.driver.session() as session:
            # 배치 노드 생성
            session.run(
                """
                UNWIND $batch AS item
                MERGE (c:Constraint {id: item.id})
                SET c.description = item.desc,
                    c.type = item.type,
                    c.query_type = item.query_type
                """,
                batch=constraint_batch,
            )
            # 배치 관계 생성
            if rel_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MATCH (qt:QueryType {name: item.qt})
                    MATCH (c:Constraint {id: item.cid})
                    MERGE (qt)-[:HAS_CONSTRAINT]->(c)
                    """,
                    batch=rel_batch,
                )

        print(f"✅ 제약 조건 {len(CONSTRAINTS)}개 생성/병합 (배치 처리)")

    def link_rules_to_constraints(self) -> None:
        """규칙과 제약 조건 연결(기본 포함 매칭 + 키워드 기반 보강)."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:Rule), (c:Constraint)
                WHERE (r.text CONTAINS c.description) OR (r.text CONTAINS c.id)
                MERGE (r)-[:ENFORCES]->(c)
                """,
            )
            # 키워드 기반 추가 연결
            for cid, keywords in CONSTRAINT_KEYWORDS.items():
                session.run(
                    """
                    MATCH (r:Rule), (c:Constraint {id: $cid})
                    WHERE ANY(kw IN $keywords WHERE toLower(r.text) CONTAINS toLower(kw))
                    MERGE (r)-[:ENFORCES]->(c)
                    """,
                    cid=cid,
                    keywords=keywords,
                )
            result = session.run(
                "MATCH (r:Rule)-[:ENFORCES]->(c:Constraint) RETURN count(*) AS links",
            ).single()
            if result is None:
                raise RuntimeError("Failed to count rule-constraint links")
            count = result["links"]
        print(f"✅ 규칙-제약 연결 {count}개 생성/병합")

    def extract_examples(self) -> None:
        """예시 추출 (❌/⭕ 패턴) 및 중복 방지 (UNWIND 배치 처리)."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (b:Block)
                WHERE (b.content CONTAINS '❌' OR b.content CONTAINS '⭕')
                  AND size(b.content) > 10
                RETURN DISTINCT b.content AS text,
                       CASE 
                           WHEN b.content CONTAINS '❌' THEN 'negative'
                           ELSE 'positive'
                       END AS type
                """,
            )

            # 배치 데이터 수집
            examples_batch: list[dict[str, str]] = []
            for record in result:
                text = record["text"]
                ex_type = record["type"]
                eid = f"example_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
                examples_batch.append({"id": eid, "text": text, "type": ex_type})

            # 배치 삽입
            if examples_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MERGE (e:Example {id: item.id})
                    SET e.text = item.text,
                        e.type = item.type,
                        e.extracted_at = datetime()
                    """,
                    batch=examples_batch,
                )

            print(f"✅ 예시 {len(examples_batch)}개 추출/병합 (배치 처리)")
            if examples_batch:
                print("샘플:")
                for ex in examples_batch[:3]:
                    print(f"   [{ex['type']}] {ex['text'][:50]}...")

    def link_examples_to_rules(self) -> None:
        """예시와 규칙 연결 (텍스트 포함 + 수동 매핑 기반, UNWIND 배치 처리)."""
        with self.driver.session() as session:
            # 긍정 예시: DEMONSTRATES
            session.run(
                """
                MATCH (e:Example {type: 'positive'}), (r:Rule)
                WHERE e.text CONTAINS r.text OR r.text CONTAINS e.text
                MERGE (e)-[:DEMONSTRATES]->(r)
                """,
            )
            # 부정 예시: VIOLATES
            session.run(
                """
                MATCH (e:Example {type: 'negative'}), (r:Rule)
                WHERE e.text CONTAINS r.text OR r.text CONTAINS e.text
                MERGE (e)-[:VIOLATES]->(r)
                """,
            )

            # 수동 매핑 테이블 배치 처리
            mapping_batch = [
                {"ex_id": ex_id, "rule_id": rule_id}
                for ex_id, rule_id in EXAMPLE_RULE_MAPPINGS.items()
            ]
            if mapping_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MATCH (e:Example {id: item.ex_id}), (r:Rule {id: item.rule_id})
                    MERGE (e)-[:DEMONSTRATES]->(r)
                    """,
                    batch=mapping_batch,
                )

            result = session.run(
                """
                MATCH (e:Example)-[rel]->(r:Rule)
                RETURN count(rel) AS links
                """,
            ).single()
            if result is None:
                raise RuntimeError("Failed to count example-rule links")
            count = result["links"]
        print(f"✅ 예시-규칙 연결 {count}개 생성/병합 (배치 처리)")

    def create_templates(self) -> None:
        """템플릿 노드 및 제약/규칙 연결 (UNWIND 배치 처리)."""
        # 배치 데이터 수집
        tmpl_batch = [{"id": t["id"], "name": t["name"]} for t in TEMPLATES]
        enforces_batch: list[dict[str, str]] = []
        includes_batch: list[dict[str, str]] = []

        for tmpl in TEMPLATES:
            enforces_batch.extend(
                {"tid": tmpl["id"], "cid": cid} for cid in tmpl["enforces"]
            )
            includes_batch.extend(
                {"tid": tmpl["id"], "cid": cid} for cid in tmpl.get("includes", [])
            )

        with self.driver.session() as session:
            # 템플릿 노드 배치 생성
            session.run(
                """
                UNWIND $batch AS item
                MERGE (t:Template {id: item.id})
                SET t.name = item.name
                """,
                batch=tmpl_batch,
            )
            # ENFORCES 관계 배치 생성
            if enforces_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MATCH (t:Template {id: item.tid}), (c:Constraint {id: item.cid})
                    MERGE (t)-[:ENFORCES]->(c)
                    """,
                    batch=enforces_batch,
                )
            # INCLUDES 관계 배치 생성
            if includes_batch:
                session.run(
                    """
                    UNWIND $batch AS item
                    MATCH (t:Template {id: item.tid}), (c:Constraint {id: item.cid})
                    MERGE (t)-[:INCLUDES]->(c)
                    """,
                    batch=includes_batch,
                )
        print(f"✅ 템플릿 {len(TEMPLATES)}개 생성/연결 (배치 처리)")

    def create_error_patterns(self) -> None:
        """금지 패턴 노드 생성 (UNWIND 배치 처리)."""
        with self.driver.session() as session:
            batch = [
                {"id": p["id"], "pattern": p["pattern"], "desc": p["description"]}
                for p in ERROR_PATTERNS
            ]
            session.run(
                """
                UNWIND $batch AS item
                MERGE (e:ErrorPattern {id: item.id})
                SET e.pattern = item.pattern,
                    e.description = item.desc
                """,
                batch=batch,
            )
        print(f"✅ 금지 패턴 {len(ERROR_PATTERNS)}개 생성/병합 (배치 처리)")

    def create_best_practices(self) -> None:
        """모범 사례 노드 생성 (UNWIND 배치 처리)."""
        with self.driver.session() as session:
            # 1. Create BestPractice nodes in batch
            node_batch = [{"id": bp["id"], "text": bp["text"]} for bp in BEST_PRACTICES]
            session.run(
                """
                UNWIND $batch AS item
                MERGE (b:BestPractice {id: item.id})
                SET b.text = item.text
                """,
                batch=node_batch,
            )
            # 2. Create APPLIES_TO relationships in batch
            rel_batch = [
                {"id": bp["id"], "qt": bp["applies_to"]} for bp in BEST_PRACTICES
            ]
            session.run(
                """
                UNWIND $batch AS item
                MATCH (b:BestPractice {id: item.id}), (q:QueryType {name: item.qt})
                MERGE (b)-[:APPLIES_TO]->(q)
                """,
                batch=rel_batch,
            )
        print(f"✅ 모범 사례 {len(BEST_PRACTICES)}개 생성/연결 (배치 처리)")

    def link_rules_to_query_types(self) -> None:
        """Rule을 QueryType과 연계 (키워드 기반 배치 매핑)."""
        # 키워드 배치 수집
        keyword_batch = [
            {"qt": qt, "keywords": keywords}
            for qt, keywords in QUERY_TYPE_KEYWORDS.items()
        ]
        with self.driver.session() as session:
            for item in keyword_batch:
                session.run(
                    """
                    MATCH (r:Rule), (q:QueryType {name: $qt})
                    WHERE ANY(kw IN $keywords WHERE toLower(r.text) CONTAINS toLower(kw))
                    MERGE (r)-[:APPLIES_TO]->(q)
                    """,
                    qt=item["qt"],
                    keywords=item["keywords"],
                )
        print("✅ Rule→QueryType 매핑 (키워드 확장) 완료")


def main() -> None:
    """QA 그래프 스키마 구축 메인 함수."""
    uri = require_env("NEO4J_URI")
    user = require_env("NEO4J_USER")
    password = require_env("NEO4J_PASSWORD")

    builder = QAGraphBuilder(uri, user, password)
    try:
        print("🔨 QA 그래프 스키마 구축 중...\n")
        builder.create_schema_constraints()
        builder.extract_rules_from_notion()
        builder.extract_query_types()
        builder.extract_constraints()
        builder.create_templates()
        builder.link_rules_to_constraints()
        builder.link_rules_to_query_types()
        builder.extract_examples()
        builder.link_examples_to_rules()
        builder.create_error_patterns()
        builder.create_best_practices()
        print("\n✅ QA 그래프 구축 완료!")
    except Neo4jError as e:
        print(f"❌ Neo4j 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 예기치 못한 오류: {e}")
        sys.exit(1)
    finally:
        builder.close()


if __name__ == "__main__":
    main()
