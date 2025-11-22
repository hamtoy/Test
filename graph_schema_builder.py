from __future__ import annotations

import os
import sys
import hashlib

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from dotenv import load_dotenv

load_dotenv()


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class QAGraphBuilder:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        if self.driver:
            self.driver.close()

    def create_schema_constraints(self):
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
        print("✅ 스키마 고유 제약 생성/확인 완료")

    def extract_rules_from_notion(self):
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
            with open("debug_log.txt", "w", encoding="utf-8") as f:
                f.write(f"DEBUG: Found {len(headings)} headings\n")

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

                with open("debug_log.txt", "a", encoding="utf-8") as f:
                    f.write(
                        f"DEBUG: Found {len(siblings_list)} siblings for heading {h['section']}\n"
                    )

                current_rules = []
                for sib in siblings_list:
                    with open("debug_log.txt", "a", encoding="utf-8") as f:
                        f.write(f"DEBUG: Processing sibling {sib['type']}\n")

                    # Stop at next heading
                    if sib["type"] in ["heading_1", "heading_2", "heading_3"]:
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
                        desc_list = list(descendants)
                        with open("debug_log.txt", "a", encoding="utf-8") as f:
                            f.write(
                                f"DEBUG: Found {len(desc_list)} descendants in container\n"
                            )

                        for d in desc_list:
                            current_rules.append(d["content"])

                # 3. Create Rule nodes
                for rule_text in current_rules:
                    if not rule_text or len(rule_text) <= 10:
                        with open("debug_log.txt", "a", encoding="utf-8") as f:
                            f.write(f"DEBUG: Skipping short rule: {rule_text}\n")
                        continue

                    with open("debug_log.txt", "a", encoding="utf-8") as f:
                        f.write(f"DEBUG: Creating rule: {rule_text[:20]}...\n")

                    # 텍스트 해시 기반 ID로 중복 방지
                    rid = hashlib.sha256(rule_text.encode("utf-8")).hexdigest()[:16]
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

    def extract_query_types(self):
        """질의 유형 정의 추출."""
        query_types = [
            {
                "name": "explanation",
                "korean": "전체 설명문",
                "limit": 1,
                "requires_reconstruction": True,
            },
            {
                "name": "summary",
                "korean": "전체 요약문",
                "limit": 1,
                "requires_reconstruction": True,
            },
            {
                "name": "target",
                "korean": "이미지 내 타겟",
                "limit": None,
                "requires_reconstruction": False,
            },
            {
                "name": "reasoning",
                "korean": "추론 질의",
                "limit": 1,
                "requires_reconstruction": False,
            },
        ]
        with self.driver.session() as session:
            for qt in query_types:
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
        print(f"✅ 질의 유형 {len(query_types)}개 생성/병합")

    def extract_constraints(self):
        """제약 조건 추출."""
        constraints = [
            {
                "id": "session_turns",
                "description": "세션당 3-4턴만 허용",
                "type": "count",
                "min": 3,
                "max": 4,
            },
            {
                "id": "explanation_summary_limit",
                "description": "설명문/요약문 중 하나만 포함",
                "type": "exclusivity",
                "exception": "4턴 세션에서만 둘 다 허용",
            },
            {
                "id": "calculation_limit",
                "description": "계산 요청 질의 1회 제한",
                "type": "count",
                "max": 1,
            },
            {
                "id": "table_chart_prohibition",
                "description": "표/그래프 참조 금지",
                "type": "prohibition",
                "pattern": r"(표|그래프)(에 따르면|에서)",
            },
        ]
        with self.driver.session() as session:
            for c in constraints:
                session.run(
                    """
                    MERGE (c:Constraint {id: $id})
                    SET c.description = $desc,
                        c.type = $type,
                        c += $props
                    """,
                    id=c["id"],
                    desc=c["description"],
                    type=c["type"],
                    props=c,
                )
        print(f"✅ 제약 조건 {len(constraints)}개 생성/병합")

    def link_rules_to_constraints(self):
        """규칙과 제약 조건 연결."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (r:Rule), (c:Constraint)
                WHERE (r.text CONTAINS c.description) OR (r.text CONTAINS c.id)
                MERGE (r)-[:ENFORCES]->(c)
                """
            )
            count = session.run(
                "MATCH (r:Rule)-[:ENFORCES]->(c:Constraint) RETURN count(*) AS links"
            ).single()["links"]
        print(f"✅ 규칙-제약 연결 {count}개 생성/병합")

    def extract_examples(self):
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
                eid = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
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

    def link_examples_to_rules(self):
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

            # 수동 매핑 테이블 (필요 시 채워서 명시적 연결)
            manual_mappings = [
                # {"ex_id": "ex_<hash>", "rule_id": "<rule_id>"},
            ]
            for m in manual_mappings:
                session.run(
                    """
                    MATCH (e:Example {id: $ex_id}), (r:Rule {id: $rule_id})
                    MERGE (e)-[:DEMONSTRATES]->(r)
                    """,
                    ex_id=m["ex_id"],
                    rule_id=m["rule_id"],
                )

            count = session.run(
                """
                MATCH (e:Example)-[rel]->(r:Rule)
                RETURN count(rel) AS links
                """
            ).single()["links"]
        print(f"✅ 예시-규칙 연결 {count}개 생성/병합 (수동 매핑 포함)")

    def create_templates(self):
        """템플릿 노드 및 제약/규칙 연결."""
        templates = [
            {
                "id": "tmpl_explanation",
                "name": "explanation_system",
                "enforces": ["session_turns", "table_chart_prohibition"],
                "includes": [],
            },
            {
                "id": "tmpl_summary",
                "name": "summary_system",
                "enforces": [
                    "session_turns",
                    "table_chart_prohibition",
                    "explanation_summary_limit",
                ],
                "includes": [],
            },
            {
                "id": "tmpl_target",
                "name": "target_user",
                "enforces": ["calculation_limit", "table_chart_prohibition"],
                "includes": [],
            },
            {
                "id": "tmpl_reasoning",
                "name": "reasoning_system",
                "enforces": ["session_turns", "table_chart_prohibition"],
                "includes": [],
            },
        ]
        with self.driver.session() as session:
            for tmpl in templates:
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
        print(f"✅ 템플릿 {len(templates)}개 생성/연결")

    def create_error_patterns(self):
        """금지 패턴 노드 생성."""
        patterns = [
            {
                "id": "err_table_ref",
                "pattern": "(표|그래프)(에 따르면|에서)",
                "description": "표/그래프 참조",
            },
            {
                "id": "err_definition",
                "pattern": "용어\\s*(정의|설명)",
                "description": "용어 정의 질문",
            },
            {
                "id": "err_full_image",
                "pattern": "전체\\s*이미지\\s*(설명|요약)",
                "description": "전체 이미지 설명/요약",
            },
        ]
        with self.driver.session() as session:
            for p in patterns:
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
        print(f"✅ 금지 패턴 {len(patterns)}개 생성/병합")

    def create_best_practices(self):
        """모범 사례 노드 생성."""
        practices = [
            {
                "id": "bp_explanation",
                "text": "전체 본문을 재구성하되 고유명/숫자 그대로 유지",
                "applies_to": "explanation",
            },
            {
                "id": "bp_summary",
                "text": "설명의 20-30% 길이로 핵심만 요약",
                "applies_to": "summary",
            },
            {
                "id": "bp_reasoning",
                "text": "명시되지 않은 전망을 근거 기반으로 묻기",
                "applies_to": "reasoning",
            },
            {
                "id": "bp_target",
                "text": "중복 위치 피하고 단일 명확한 타겟 질문",
                "applies_to": "target",
            },
        ]
        with self.driver.session() as session:
            for bp in practices:
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
        print(f"✅ 모범 사례 {len(practices)}개 생성/연결")

    def link_rules_to_query_types(self):
        """Rule을 QueryType과 연계 (키워드 기반 간단 매핑)."""
        mappings = [
            ("explanation", ["전체 설명", "설명문", "full explanation", "본문 전체"]),
            ("summary", ["요약", "summary", "짧게"]),
            ("target", ["질문", "타겟", "target", "단일 항목"]),
            ("reasoning", ["추론", "전망", "예측", "분석"]),
        ]
        with self.driver.session() as session:
            for qt, keywords in mappings:
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


def main():
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
