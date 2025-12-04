"""잘못 분류된 Constraint 노드 정리 스크립트.

schema.py에 정의된 4개 공식 Constraint만 남기고
나머지 12개 (ID=NULL, Rule로 분류되어야 함)를 삭제합니다.
"""

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


def cleanup_misclassified_constraints(dry_run=True):
    """잘못 분류된 Constraint 노드 정리."""
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
                print("🔍 DRY RUN: 삭제 대상 미리보기")
            else:
                print("🗑️  Constraint 노드 정리 실행")
            print("=" * 70)

            # 현재 상태 확인
            result = session.run("MATCH (c:Constraint) RETURN count(c) as total")
            total_before = result.single()["total"]
            print(f"\n현재 Constraint 노드: {total_before}개")

            # 삭제 대상 확인
            result = session.run(
                """
                MATCH (c:Constraint)
                WHERE c.id IS NULL OR NOT c.id IN $official_ids
                RETURN elementId(c) as element_id,
                       c.id as id,
                       c.description as description,
                       c.query_type as query_type,
                       c.priority as priority
                ORDER BY c.priority DESC
            """,
                official_ids=list(OFFICIAL_IDS),
            )

            to_delete = list(result)
            print(f"삭제 대상 노드: {len(to_delete)}개\n")

            if not to_delete:
                print("✅ 삭제할 노드가 없습니다. 이미 정리되어 있습니다!")
                return

            # 삭제 대상 출력
            print("삭제될 노드 목록:")
            print("-" * 70)
            for i, node in enumerate(to_delete, 1):
                node_id = node["id"] or "NULL"
                desc = node["description"] or "N/A"
                qt = node["query_type"] or "NULL"
                priority = node["priority"] or "N/A"

                # description 미리보기 (50자)
                desc_preview = (desc[:50] + "...") if len(str(desc)) > 50 else desc

                print(f"\n[{i}] ID: {node_id}")
                print(f"    query_type: {qt}")
                print(f"    priority: {priority}")
                print(f"    description: {desc_preview}")

            if dry_run:
                print(f"\n{'=' * 70}")
                print("ℹ️  DRY RUN 모드입니다. 실제 삭제를 원하시면:")
                print("   python scripts/cleanup_misclassified_constraints.py --delete")
                print("=" * 70)
                return

            # 실제 삭제 실행
            print(f"\n{'=' * 70}")
            print("🗑️  삭제 실행 중...")
            print("=" * 70)

            for i, node in enumerate(to_delete, 1):
                element_id = node["element_id"]
                node_id = node["id"] or "NULL"

                session.run(
                    """
                    MATCH (c:Constraint)
                    WHERE elementId(c) = $element_id
                    DETACH DELETE c
                """,
                    element_id=element_id,
                )

                print(f"   ✓ [{i}/{len(to_delete)}] {node_id} 삭제됨")

            print(f"\n✅ {len(to_delete)}개 노드 삭제 완료!")

            # 검증
            print(f"\n{'=' * 70}")
            print("🔍 검증")
            print("=" * 70)

            result = session.run("MATCH (c:Constraint) RETURN count(c) as total")
            total_after = result.single()["total"]

            print(f"\n삭제 전: {total_before}개")
            print(f"삭제 후: {total_after}개")
            print(f"삭제됨: {total_before - total_after}개")

            # 남은 노드 확인
            print("\n남은 Constraint 노드:")
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.id as id, c.description as description, c.query_type as qt
                ORDER BY c.id
            """)

            for record in result:
                node_id = record["id"]
                desc = record["description"]
                qt = record["qt"] or "NULL (전역)"

                status = "✅" if node_id in OFFICIAL_IDS else "⚠️"
                print(f"   {status} {node_id:30} | {qt:15} | {desc[:40]}...")

            if total_after == len(OFFICIAL_IDS):
                print(
                    f"\n✅ 성공! schema.py의 {len(OFFICIAL_IDS)}개 공식 Constraint만 남았습니다!"
                )
            else:
                print(f"\n⚠️  예상과 다릅니다. {total_after}개가 남아있습니다.")

    finally:
        driver.close()


if __name__ == "__main__":
    import sys

    # 기본값은 DRY RUN
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--delete":
        dry_run = False
        print("\n⚠️  경고: 실제 삭제 모드입니다!")
        print("계속하시려면 5초 안에 Ctrl+C를 누르지 마세요...\n")
        import time

        time.sleep(3)

    cleanup_misclassified_constraints(dry_run=dry_run)
