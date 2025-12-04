# mypy: ignore-errors
"""Neo4j 데이터 확인 및 수동 매핑 가능성 체크."""

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

print("=" * 80)
print("Neo4j 데이터 확인 - 수동 매핑 가능성 체크")
print("=" * 80)

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # 1. Rule 노드 확인
        print("\n📋 1. Rule 노드 목록")
        print("-" * 80)
        rule_query = """
        MATCH (r:Rule)
        OPTIONAL MATCH (r)-[:APPLIES_TO]->(qt:QueryType)
        RETURN r.rule_id as id, r.text as text, r.source as source, 
               collect(DISTINCT qt.name) as types
        ORDER BY r.rule_id
        """
        rules = list(session.run(rule_query))
        print(f"총 {len(rules)}개 Rule")
        for i, record in enumerate(rules, 1):
            print(f"\n[{i}] {record['id']}")
            print(f"    텍스트: {record['text'][:80]}...")
            print(f"    소스: {record['source']}")
            print(
                f"    적용 타입: {', '.join(record['types']) if record['types'] else 'None'}"
            )

        # 2. Example 노드 확인
        print("\n\n📝 2. Example 노드 샘플 (최대 20개)")
        print("-" * 80)
        example_query = """
        MATCH (e:Example)
        OPTIONAL MATCH (e)-[:DEMONSTRATES]->(r:Rule)
        RETURN e.example_id as id, e.text as text, e.is_good as is_good,
               collect(r.rule_id) as rules
        ORDER BY e.example_id
        LIMIT 20
        """
        examples = list(session.run(example_query))
        print(f"총 Example: {len(examples)}개 (샘플만 표시)")
        for i, record in enumerate(examples, 1):
            status = "✅ 좋은 예" if record["is_good"] else "❌ 나쁜 예"
            print(f"\n[{i}] {record['id']} - {status}")
            print(f"    텍스트: {record['text'][:80]}...")
            print(
                f"    연결된 Rule: {', '.join(record['rules']) if record['rules'] else '없음'}"
            )

        # 3. Constraint 노드 확인
        print("\n\n⚠️ 3. Constraint 노드 샘플 (최대 20개)")
        print("-" * 80)
        constraint_query = """
        MATCH (c:Constraint)
        OPTIONAL MATCH (c)-[:APPLIES_TO]->(qt:QueryType)
        RETURN c.constraint_id as id, c.description as desc, c.category as category,
               collect(qt.name) as types
        ORDER BY c.constraint_id
        LIMIT 20
        """
        constraints = list(session.run(constraint_query))
        print(f"총 Constraint: {len(constraints)}개 (샘플만 표시)")
        for i, record in enumerate(constraints, 1):
            print(f"\n[{i}] {record['id']}")
            print(f"    설명: {record['desc'][:80]}...")
            print(f"    카테고리: {record['category']}")
            print(
                f"    적용 타입: {', '.join(record['types']) if record['types'] else 'None'}"
            )

        # 4. 전체 통계
        print("\n\n📊 4. 전체 통계")
        print("-" * 80)
        stats_query = """
        MATCH (r:Rule) WITH count(r) as rule_count
        MATCH (e:Example) WITH rule_count, count(e) as example_count
        MATCH (c:Constraint) WITH rule_count, example_count, count(c) as constraint_count
        MATCH ()-[rel:DEMONSTRATES]->() WITH rule_count, example_count, constraint_count, count(rel) as demo_count
        MATCH ()-[rel2:APPLIES_TO]->() 
        RETURN rule_count, example_count, constraint_count, demo_count, count(rel2) as applies_count
        """
        stats = session.run(stats_query).single()
        print(f"Rule 노드: {stats['rule_count']}개")
        print(f"Example 노드: {stats['example_count']}개")
        print(f"Constraint 노드: {stats['constraint_count']}개")
        print(f"DEMONSTRATES 관계: {stats['demo_count']}개")
        print(f"APPLIES_TO 관계: {stats['applies_count']}개")

        # 5. 매핑되지 않은 Example 확인
        print("\n\n🔍 5. 매핑되지 않은 Example (Rule과 연결 안 됨)")
        print("-" * 80)
        unmapped_query = """
        MATCH (e:Example)
        WHERE NOT (e)-[:DEMONSTRATES]->(:Rule)
        RETURN e.example_id as id, e.text as text, e.is_good as is_good
        ORDER BY e.example_id
        LIMIT 10
        """
        unmapped = list(session.run(unmapped_query))
        print(f"매핑 안 된 Example: {len(unmapped)}개 (샘플 10개)")
        for i, record in enumerate(unmapped, 1):
            status = "✅" if record["is_good"] else "❌"
            print(f"\n[{i}] {status} {record['id']}")
            print(f"    {record['text'][:100]}...")

        # 6. 수동 매핑 가능성 판단
        print("\n\n✅ 6. 수동 매핑 가능성")
        print("-" * 80)
        total_examples = stats["example_count"]
        mapped_examples = stats["demo_count"]
        unmapped_count = total_examples - mapped_examples

        print(f"전체 Example: {total_examples}개")
        print(f"이미 매핑됨: {mapped_examples}개")
        print(f"매핑 필요: {unmapped_count}개")

        if unmapped_count == 0:
            print("\n✅ 모든 Example이 이미 매핑되어 있습니다!")
        elif unmapped_count <= 50:
            print(
                f"\n✅ 수동 매핑 가능! ({unmapped_count}개는 충분히 수동으로 매핑 가능합니다)"
            )
        elif unmapped_count <= 200:
            print(f"\n⚠️  수동 매핑 가능하지만 시간이 걸림 ({unmapped_count}개)")
        else:
            print(f"\n❌ 수동 매핑 어려움 ({unmapped_count}개는 자동화 필요)")

        # 7. 매핑 템플릿 제공
        if unmapped_count > 0 and unmapped_count <= 50:
            print("\n\n📝 7. 수동 매핑 Cypher 템플릿")
            print("-" * 80)
            print("""
// 매핑 예시:
MATCH (e:Example {example_id: "example_id_here"})
MATCH (r:Rule {rule_id: "rule_id_here"})
MERGE (e)-[:DEMONSTRATES]->(r)

// 또는 배치 매핑:
UNWIND [
  {example: "example_1", rule: "fmt_no_md"},
  {example: "example_2", rule: "len_target_short"}
] AS mapping
MATCH (e:Example {example_id: mapping.example})
MATCH (r:Rule {rule_id: mapping.rule})
MERGE (e)-[:DEMONSTRATES]->(r)
""")

    driver.close()
    print("\n" + "=" * 80)
    print("완료!")

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
