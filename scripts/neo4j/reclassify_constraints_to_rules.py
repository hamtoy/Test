"""Constraint → Rule 노드 변환 스크립트.

잘못 분류된 12개 Constraint를 Rule 노드로 변환합니다.
데이터를 보존하면서 올바른 노드 타입으로 재분류합니다.
"""

import hashlib
import os
import sys

from neo4j import GraphDatabase

# schema.py에 정의된 공식 Constraint ID들
OFFICIAL_IDS = {
    "session_turns",
    "explanation_summary_limit",
    "calculation_limit",
    "table_chart_prohibition",
}


def reclassify_constraints_to_rules(dry_run=True):
    """Constraint를 Rule로 재분류."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 Neo4j 연결: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session() as session:
            print("=" * 70)
            if dry_run:
                print("🔍 DRY RUN: 변환 대상 미리보기")
            else:
                print("🔄 Constraint → Rule 변환 실행")
            print("=" * 70)

            # 변환 대상 조회
            result = session.run(
                """
                MATCH (c:Constraint)
                WHERE c.id IS NULL OR NOT c.id IN $official_ids
                RETURN elementId(c) as element_id,
                       c.id as id,
                       c.description as description,
                       c.query_type as query_type,
                       c.priority as priority,
                       c.category as category,
                       c.applies_to as applies_to,
                       c.name as name,
                       properties(c) as all_props
                ORDER BY c.priority DESC
            """,
                official_ids=list(OFFICIAL_IDS),
            )

            to_convert = list(result)
            print(f"\n변환 대상 노드: {len(to_convert)}개\n")

            if not to_convert:
                print("✅ 변환할 노드가 없습니다!")
                return

            # 변환 계획 출력
            conversions = []
            for i, node in enumerate(to_convert, 1):
                # Rule ID 생성 (description 기반 해시)
                description = node["description"] or ""
                rule_id = f"rule_{hashlib.sha256(description.encode('utf-8')).hexdigest()[:16]}"

                conversion = {
                    "element_id": node["element_id"],
                    "old_id": node["id"] or "NULL",
                    "new_rule_id": rule_id,
                    "description": description,
                    "query_type": node["query_type"],
                    "priority": node["priority"],
                    "category": node["category"],
                    "applies_to": node["applies_to"],
                    "name": node["name"],
                    "all_props": node["all_props"],
                }
                conversions.append(conversion)

                desc_preview = (
                    (description[:60] + "...") if len(description) > 60 else description
                )
                print(f"[{i}] Constraint (NULL) → Rule ({rule_id})")
                print(f"    query_type: {conversion['query_type']}")
                print(f"    priority: {conversion['priority']}")
                print(f"    내용: {desc_preview}\n")

            if dry_run:
                print(f"{'=' * 70}")
                print("ℹ️  DRY RUN 모드입니다. 실제 변환을 원하시면:")
                print("   python scripts/reclassify_constraints_to_rules.py --convert")
                print("=" * 70)
                return

            # 실제 변환 실행
            print(f"{'=' * 70}")
            print("🔄 변환 실행 중...")
            print("=" * 70)

            created_rules = 0
            deleted_constraints = 0

            for i, conv in enumerate(conversions, 1):
                # 1. Rule 노드 생성
                session.run(
                    """
                    MERGE (r:Rule {id: $rule_id})
                    SET r.text = $description,
                        r.query_type = $query_type,
                        r.priority = $priority,
                        r.category = $category,
                        r.applies_to = $applies_to,
                        r.name = $name,
                        r.converted_from = 'Constraint',
                        r.converted_at = datetime()
                """,
                    rule_id=conv["new_rule_id"],
                    description=conv["description"],
                    query_type=conv["query_type"],
                    priority=conv["priority"],
                    category=conv["category"],
                    applies_to=conv["applies_to"],
                    name=conv["name"],
                )
                created_rules += 1

                # 2. 원본 Constraint 삭제
                session.run(
                    """
                    MATCH (c:Constraint)
                    WHERE elementId(c) = $element_id
                    DETACH DELETE c
                """,
                    element_id=conv["element_id"],
                )
                deleted_constraints += 1

                print(
                    f"   ✓ [{i}/{len(conversions)}] {conv['old_id']} → {conv['new_rule_id']}"
                )

            print("\n✅ 변환 완료!")
            print(f"   Rule 생성: {created_rules}개")
            print(f"   Constraint 삭제: {deleted_constraints}개")

            # 검증
            print(f"\n{'=' * 70}")
            print("🔍 검증")
            print("=" * 70)

            # Constraint 개수 확인
            result = session.run("MATCH (c:Constraint) RETURN count(c) as cnt")
            constraint_count = result.single()["cnt"]

            # Rule 개수 확인
            result = session.run("MATCH (r:Rule) RETURN count(r) as cnt")
            rule_count = result.single()["cnt"]

            print("\n현재 상태:")
            print(f"   Constraint 노드: {constraint_count}개")
            print(f"   Rule 노드: {rule_count}개")

            if constraint_count == len(OFFICIAL_IDS):
                print(
                    f"\n✅ 성공! schema.py의 {len(OFFICIAL_IDS)}개 공식 Constraint만 남았습니다!"
                )
            else:
                print(
                    f"\n⚠️  Constraint가 {constraint_count}개입니다. 예상: {len(OFFICIAL_IDS)}개"
                )

            # 남은 Constraint 확인
            print("\n남은 Constraint:")
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.id as id, c.description as desc, c.query_type as qt
                ORDER BY c.id
            """)

            for record in result:
                node_id = record["id"]
                qt = record["qt"] or "NULL"

                status = "✅" if node_id in OFFICIAL_IDS else "⚠️"
                print(f"   {status} {node_id:30} | {qt:10}")

    finally:
        driver.close()


if __name__ == "__main__":
    import sys

    # 기본값은 DRY RUN
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--convert":
        dry_run = False
        print("\n⚠️  주의: Constraint를 Rule로 변환합니다!")
        print("계속하시려면 3초 안에 Ctrl+C를 누르지 마세요...\n")
        import time

        time.sleep(2)

    reclassify_constraints_to_rules(dry_run=dry_run)
