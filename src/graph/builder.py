"""QA 그래프 빌더."""

from __future__ import annotations

import hashlib
import logging
import sys
from typing import Any, Dict, List

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
                "CREATE CONSTRAINT rule_id_unique IF NOT EXISTS FOR (r:Rule) REQUIRE r.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT constraint_id_unique IF NOT EXISTS FOR (c:Constraint) REQUIRE c.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT example_id_unique IF NOT EXISTS FOR (e:Example) REQUIRE e.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT qtype_name_unique IF NOT EXISTS FOR (q:QueryType) REQUIRE q.name IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT template_id_unique IF NOT EXISTS FOR (t:Template) REQUIRE t.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT errorpattern_id_unique IF NOT EXISTS FOR (e:ErrorPattern) REQUIRE e.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT bestpractice_id_unique IF NOT EXISTS FOR (b:BestPractice) REQUIRE b.id IS UNIQUE"
            )
        self.logger.info("스키마 고유 제약 생성/확인 완료")

    def extract_rules_from_notion(self) -> None:
        """Notion 문서에서 규칙 추출 및 그래프화 (중복 방지 MERGE)."""
        with self.driver.session() as session:
            # 1. Find headings
            headings = session.run(
                """
                MATCH (p:Page)-[:HAS_BLOCK]->(h:Block)
                WHERE h.type = 'heading_1' AND h.content CONTAINS '자주 틀리는'
                RETURN p.id as page_id, h.order as start_order, h.content as section
                """
            ).data()

            created = 0
            for h in headings:
                # 2. Fetch subsequent top-level blocks
                siblings = session.run(
                    """
                    MATCH (p:Page {id: $page_id})-[:HAS_BLOCK]->(b:Block)
                    WHERE b.order > $start_order
                    RETURN b.id as id, b.content as content, b.type as type
                    ORDER BY b.order ASC
                    """,
                    page_id=h["page_id"],
                    start_order=h["start_order"],
                )
                siblings_list = list(siblings)

                current_rules = []
                for sib in siblings_list:
                    # Stop at next major heading only (allow subsections)
                    if sib["type"] == "heading_1":
                        break

                    # If content block, add
                    if sib["type"] in ["paragraph", "bulleted_list_item", "callout"]:
                        current_rules.append(sib["content"])

                    # If container, fetch descendants
                    elif sib["type"] in ["column_list", "column"]:
                        descendants = session.run(
                            """
                            MATCH (b:Block {id: $id})-[:HAS_CHILD*]->(d:Block)
                            WHERE d.type IN ['paragraph', 'bulleted_list_item', 'callout']
                            RETURN d.content as content
                            """,
                            id=sib["id"],
                        )
                        desc_list: List[Dict[str, Any]] = [dict(d) for d in descendants]
                        current_rules.extend(
                            d.get("content", "") for d in desc_list if d.get("content")
                        )

                # 3. Create Rule nodes
                for rule_text in current_rules:
                    if not rule_text or len(rule_text) <= 10:
                        continue

                    # 접두사를 포함한 해시 기반 ID로 중복 방지
                    rid = f"rule_{hashlib.sha256(rule_text.encode('utf-8')).hexdigest()[:16]}"
                    session.run(
                        """
                        MERGE (r:Rule {id: $id})
                        SET r.text = $text,
                            r.section = $section,
                            r.priority = 'high'
                        """,
                        id=rid,
                        text=rule_text,
                        section=h["section"],
                    )
                    created += 1
            print(f"✅ 규칙 {created}개 추출/병합 완료")

    def extract_query_types(self) -> None:
        """질의 유형 정의 추출."""
        with self.driver.session() as session:
            for qt in QUERY_TYPES:
                session.run(
                    """
                    MERGE (q:QueryType {name: $name})
                    SET q.korean = $korean,
                        q.session_limit = $limit,
                        q.requires_reconstruction = $reconstruction
                    """,
                    name=qt["name"],
                    korean=qt["korean"],
                    limit=qt["limit"],
                    reconstruction=qt["requires_reconstruction"],
                )
        print(f"✅ 질의 유형 {len(QUERY_TYPES)}개 생성/병합")

    def extract_constraints(self) -> None:
        """제약 조건 추출 및 query_type 자동 설정.

        TEMPLATES의 enforces 관계를 분석하여 각 Constraint가
        어떤 query_type에서 사용되는지 자동으로 매핑합니다.
        """
        # 1. Constraint를 사용하는 Template 매핑 생성
        constraint_to_query_types: Dict[str, List[str]] = {}

        for template in TEMPLATES:
            # template['name']에서 query_type 추출
            # 예: "explanation_system" -> "explanation"
            # "target_user" -> "target"
            template_name = template["name"]
            query_type = template_name.split("_")[0]  # 첫 번째 부분이 query_type

            # 이 템플릿이 enforce하는 모든 constraint에 query_type 매핑
            for constraint_id in template.get("enforces", []):
                if constraint_id not in constraint_to_query_types:
                    constraint_to_query_types[constraint_id] = []
                if query_type not in constraint_to_query_types[constraint_id]:
                    constraint_to_query_types[constraint_id].append(query_type)

        # 2. Constraint 생성 시 query_type 설정
        with self.driver.session() as session:
            for c in CONSTRAINTS:
                constraint_id = c["id"]
                query_types = constraint_to_query_types.get(constraint_id, [])

                # 여러 query_type에서 사용되면 첫 번째 것 사용
                # 전역 제약사항(모든 타입에서 사용)이면 None
                if not query_types or len(query_types) >= 3:
                    query_type = None
                else:
                    query_type = query_types[0]  # 첫 번째 query_type 사용

                session.run(
                    """
                    MERGE (c:Constraint {id: $id})
                    SET c.description = $desc,
                        c.type = $type,
                        c.query_type = $query_type,
                        c += $props
                    """,
                    id=constraint_id,
                    desc=c["description"],
                    type=c["type"],
                    query_type=query_type,
                    props=c,
                )

                # 로깅
                qt_display = query_type or "전역"
                self.logger.debug(
                    f"Constraint '{constraint_id}' -> query_type: {qt_display}"
                )

        print(f"✅ 제약 조건 {len(CONSTRAINTS)}개 생성/병합 (query_type 자동 설정)")

    def link_rules_to_constraints(self) -> None:
        """규칙과 제약 조건 연결(기본 포함 매칭 + 키워드 기반 보강)."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:Rule), (c:Constraint)
                WHERE (r.text CONTAINS c.description) OR (r.text CONTAINS c.id)
                MERGE (r)-[:ENFORCES]->(c)
                """
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
                "MATCH (r:Rule)-[:ENFORCES]->(c:Constraint) RETURN count(*) AS links"
            ).single()
            if result is None:
                raise RuntimeError("Failed to count rule-constraint links")
            count = result["links"]
        print(f"✅ 규칙-제약 연결 {count}개 생성/병합")

    def extract_examples(self) -> None:
        """예시 추출 (❌/⭕ 패턴) 및 중복 방지."""
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
                """
            )

            examples = []
            for record in result:
                text = record["text"]
                ex_type = record["type"]
                # 텍스트 해시 기반 ID로 중복 방지
                # 접두사를 포함한 해시 기반 ID로 중복 방지
                eid = f"example_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
                session.run(
                    """
                    MERGE (e:Example {id: $id})
                    SET e.text = $text,
                        e.type = $type,
                        e.extracted_at = datetime()
                    """,
                    id=eid,
                    text=text,
                    type=ex_type,
                )
                examples.append((text[:50], ex_type))

            print(f"✅ 예시 {len(examples)}개 추출/병합")
            if examples:
                print("샘플:")
                for text, t in examples[:3]:
                    print(f"   [{t}] {text}...")

    def link_examples_to_rules(self) -> None:
        """예시와 규칙 연결 (텍스트 포함 + 수동 매핑 기반)."""
        with self.driver.session() as session:
            # 긍정 예시: DEMONSTRATES
            session.run(
                """
                MATCH (e:Example {type: 'positive'}), (r:Rule)
                WHERE e.text CONTAINS r.text OR r.text CONTAINS e.text
                MERGE (e)-[:DEMONSTRATES]->(r)
                """
            )
            # 부정 예시: VIOLATES
            session.run(
                """
                MATCH (e:Example {type: 'negative'}), (r:Rule)
                WHERE e.text CONTAINS r.text OR r.text CONTAINS e.text
                MERGE (e)-[:VIOLATES]->(r)
                """
            )

            # 수동 매핑 테이블 (접두사 포함된 example_id → rule_id 매핑)
            for ex_id, rule_id in EXAMPLE_RULE_MAPPINGS.items():
                session.run(
                    """
                    MATCH (e:Example {id: $ex_id}), (r:Rule {id: $rule_id})
                    MERGE (e)-[:DEMONSTRATES]->(r)
                    """,
                    ex_id=ex_id,
                    rule_id=rule_id,
                )

            result = session.run(
                """
                MATCH (e:Example)-[rel]->(r:Rule)
                RETURN count(rel) AS links
                """
            ).single()
            if result is None:
                raise RuntimeError("Failed to count example-rule links")
            count = result["links"]
        print(f"✅ 예시-규칙 연결 {count}개 생성/병합 (수동 매핑 포함)")

    def create_templates(self) -> None:
        """템플릿 노드 및 제약/규칙 연결."""
        with self.driver.session() as session:
            for tmpl in TEMPLATES:
                session.run(
                    """
                    MERGE (t:Template {id: $id})
                    SET t.name = $name
                    """,
                    id=tmpl["id"],
                    name=tmpl["name"],
                )
                for cid in tmpl["enforces"]:
                    session.run(
                        """
                        MATCH (t:Template {id: $tid}), (c:Constraint {id: $cid})
                        MERGE (t)-[:ENFORCES]->(c)
                        """,
                        tid=tmpl["id"],
                        cid=cid,
                    )
                for cid in tmpl.get("includes", []):
                    session.run(
                        """
                        MATCH (t:Template {id: $tid}), (c:Constraint {id: $cid})
                        MERGE (t)-[:INCLUDES]->(c)
                        """,
                        tid=tmpl["id"],
                        cid=cid,
                    )
        print(f"✅ 템플릿 {len(TEMPLATES)}개 생성/연결")

    def create_error_patterns(self) -> None:
        """금지 패턴 노드 생성."""
        with self.driver.session() as session:
            for p in ERROR_PATTERNS:
                session.run(
                    """
                    MERGE (e:ErrorPattern {id: $id})
                    SET e.pattern = $pattern,
                        e.description = $desc
                    """,
                    id=p["id"],
                    pattern=p["pattern"],
                    desc=p["description"],
                )
        print(f"✅ 금지 패턴 {len(ERROR_PATTERNS)}개 생성/병합")

    def create_best_practices(self) -> None:
        """모범 사례 노드 생성."""
        with self.driver.session() as session:
            for bp in BEST_PRACTICES:
                session.run(
                    """
                    MERGE (b:BestPractice {id: $id})
                    SET b.text = $text
                    """,
                    id=bp["id"],
                    text=bp["text"],
                )
                session.run(
                    """
                    MATCH (b:BestPractice {id: $id}), (q:QueryType {name: $qt})
                    MERGE (b)-[:APPLIES_TO]->(q)
                    """,
                    id=bp["id"],
                    qt=bp["applies_to"],
                )
        print(f"✅ 모범 사례 {len(BEST_PRACTICES)}개 생성/연결")

    def link_rules_to_query_types(self) -> None:
        """Rule을 QueryType과 연계 (키워드 기반 간단 매핑)."""
        with self.driver.session() as session:
            for qt, keywords in QUERY_TYPE_KEYWORDS.items():
                session.run(
                    """
                    MATCH (r:Rule), (q:QueryType {name: $qt})
                    WHERE ANY(kw IN $keywords WHERE toLower(r.text) CONTAINS toLower(kw))
                    MERGE (r)-[:APPLIES_TO]->(q)
                    """,
                    qt=qt,
                    keywords=keywords,
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
