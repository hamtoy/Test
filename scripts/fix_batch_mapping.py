# mypy: ignore-errors
"""Example 노드의 실제 ID 필드 확인 및 수정된 배치 매핑."""

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

print("=" * 100)
print("Example 노드 ID 필드 확인 및 수정된 배치 매핑")
print("=" * 100)

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    with driver.session() as session:
        # Example 노드의 모든 속성 확인
        print("\n1. Example 노드 속성 확인 (첫 번째 노드)")
        print("-" * 100)
        props_query = """
        MATCH (e:Example)
        RETURN e LIMIT 1
        """
        first_example = session.run(props_query).single()
        if first_example:
            example_node = first_example["e"]
            print(f"속성: {dict(example_node)}")

        # 매핑 안 된 Example 조회 (모든 가능한 ID 필드 확인)
        unmapped_query = """
        MATCH (e:Example)
        WHERE NOT (e)-[:DEMONSTRATES]->(:Rule)
        RETURN e.id as id1, e.example_id as id2, e.text_hash as id3, 
               e.text as text, e.is_good as is_good, id(e) as neo4j_id
        ORDER BY neo4j_id
        LIMIT 30
        """
        unmapped = list(session.run(unmapped_query))

        if not unmapped:
            print("\n✅ 모든 Example이 이미 매핑되어 있습니다!")
            driver.close()
            exit(0)

        print(f"\n2. 매핑 안 된 Example: {len(unmapped)}개")
        print("-" * 100)

        # 실제 사용 가능한 ID 필드 찾기
        id_field = None
        for record in unmapped[:5]:
            if record["id1"]:
                id_field = "id"
                break
            elif record["id2"]:
                id_field = "example_id"
                break
            elif record["id3"]:
                id_field = "text_hash"
                break

        if not id_field:
            # Neo4j 내부 ID 사용
            id_field = "neo4j_id"
            print(f"\n⚠️  속성 ID가 없습니다. Neo4j 내부 ID 사용: {id_field}")
        else:
            print(f"\n✅ 사용할 ID 필드: e.{id_field}")

        # 매핑 생성
        mappings = []
        for i, record in enumerate(unmapped):
            # ID 값 가져오기
            if id_field == "neo4j_id":
                example_id = record["neo4j_id"]
            else:
                example_id = (
                    record["id1"]
                    or record["id2"]
                    or record["id3"]
                    or record["neo4j_id"]
                )

            text = (record["text"] or "").lower()
            is_good = record["is_good"]

            # 자동 Rule 결정
            suggested_rule = "fmt_no_md"  # 기본값

            if "**" in text or "볼드" in text or "마크다운" in text:
                suggested_rule = "fmt_no_md"
            elif ("40" in text or "한 문장" in text) and "단어" in text:
                suggested_rule = "len_target_short"
            elif "80" in text and "추론" in text:
                suggested_rule = "len_reasoning"
            elif "150" in text or ("3~5" in text and "문장" in text):
                suggested_rule = "len_explanation"
            elif "복사" in text or "중복" in text:
                suggested_rule = "dedup_reference"

            mappings.append(
                {"id": example_id, "rule": suggested_rule, "preview": text[:50]}
            )

            # 샘플 출력
            if i < 10:
                status = "✅" if is_good else "❌"
                print(f"{status} [{i + 1}] ID={example_id} → {suggested_rule}")
                print(f"    {text[:80]}...")

        print(f"\n생성된 매핑: {len(mappings)}개")

        # 배치 매핑 실행
        print("\n3. 배치 매핑 실행")
        print("-" * 100)

        if id_field == "neo4j_id":
            # Neo4j 내부 ID 사용
            batch_query = """
            UNWIND $mappings AS mapping
            MATCH (e:Example)
            WHERE id(e) = mapping.id
            MATCH (r:Rule {rule_id: mapping.rule})
            MERGE (e)-[:DEMONSTRATES]->(r)
            """
        else:
            # 속성 ID 사용
            batch_query = f"""
            UNWIND $mappings AS mapping
            MATCH (e:Example {{{id_field}: mapping.id}})
            MATCH (r:Rule {{rule_id: mapping.rule}})
            MERGE (e)-[:DEMONSTRATES]->(r)
            """

        result = session.run(batch_query, mappings=mappings)
        summary = result.consume()

        print("\n✅ 배치 매핑 완료!")
        print(f"   - 관계 생성: {summary.counters.relationships_created}개")

        # 검증
        verify_query = """
        MATCH (e:Example)-[rel:DEMONSTRATES]->(r:Rule)
        RETURN count(rel) as total
        """
        total = session.run(verify_query).single()["total"]
        print(f"\n📊 전체 DEMONSTRATES 관계: {total}개")

    driver.close()
    print("\n" + "=" * 100)
    print("완료!")

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
