"""Neo4j에 QA 규칙 등록 스크립트."""

# Neo4j 연결 정보 (환경변수 또는 .env에서 가져오기)
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

if not NEO4J_PASSWORD:
    print("ERROR: NEO4J_PASSWORD가 설정되지 않았습니다.")
    exit(1)

# 규칙 데이터
rules = [
    {
        "id": "fmt_no_md",
        "text": "볼드/이탤릭/코드블록/링크/표 금지 (강조·코드·표 없음)",
        "types": ["explanation", "reasoning", "target"],
    },
    {
        "id": "len_target_short",
        "text": "타겟 단답: 불릿 금지, 1문장 40단어 이하, 마크다운 금지",
        "types": ["target"],
    },
    {
        "id": "len_reasoning",
        "text": "추론: 1단락, 불릿·소제목 금지, 80단어 이하",
        "types": ["reasoning"],
    },
    {
        "id": "len_explanation",
        "text": "전체 설명: 3~5문장, 150단어 이하, 불릿은 허용하되 볼드/코드블록/링크/표 금지",
        "types": ["explanation"],
    },
    {
        "id": "dedup_reference",
        "text": "전체 설명문 문장 복사 금지, 표현 바꿔 요약. 전체 설명문에 없지만 OCR에만 있는 수치·팩트는 반드시 포함",
        "types": ["explanation", "reasoning", "target"],
    },
]

# Cypher 쿼리
cypher = """
UNWIND $rules AS row
MERGE (r:Rule {rule_id: row.id})
SET r.text = row.text,
    r.source = "guide/qna",
    r.updated_at = datetime()
FOREACH (qt IN row.types |
  MERGE (q:QueryType {name: qt})
  MERGE (r)-[:APPLIES_TO]->(q)
)
"""

print("=" * 60)
print("Neo4j QA 규칙 등록")
print("=" * 60)

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # 규칙 등록
        result = session.run(cypher, rules=rules)
        summary = result.consume()

        print("\n✅ 규칙 등록 완료!")
        print(f"   - 노드 생성: {summary.counters.nodes_created}")
        print(f"   - 관계 생성: {summary.counters.relationships_created}")
        print(f"   - 속성 설정: {summary.counters.properties_set}")

        # 등록된 규칙 확인
        print("\n📋 등록된 규칙:")
        verify_query = """
        MATCH (r:Rule)
        WHERE r.source = "guide/qna"
        OPTIONAL MATCH (r)-[:APPLIES_TO]->(qt:QueryType)
        RETURN r.rule_id as id, r.text as text, collect(qt.name) as types
        ORDER BY r.rule_id
        """
        verify_result = session.run(verify_query)

        for record in verify_result:
            print(f"\n   [{record['id']}]")
            print(f"   규칙: {record['text']}")
            print(f"   적용 타입: {', '.join(record['types'])}")

    driver.close()
    print("\n" + "=" * 60)
    print("완료!")

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    exit(1)
