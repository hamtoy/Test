"""Constraint 노드의 query_type 자동 수정 스크립트.

ID 패턴을 기반으로 적절한 query_type을 추론하고 설정합니다.
"""

import os
import sys

from neo4j import GraphDatabase


def infer_query_type(node_id):
    """노드 ID로부터 query_type 추론."""
    if not node_id:
        return "explanation"  # 기본값

    id_lower = node_id.lower()

    # ID 패턴 기반 매핑
    if "explanation" in id_lower or "설명" in id_lower:
        return "explanation"
    elif "reasoning" in id_lower or "추론" in id_lower or "이유" in id_lower:
        return "reasoning"
    elif "summary" in id_lower or "요약" in id_lower:
        return "summary"
    elif "target" in id_lower and "short" in id_lower:
        return "target_short"
    elif "target" in id_lower and "long" in id_lower:
        return "target_long"
    elif "session" in id_lower or "turn" in id_lower:
        # 세션/턴 관련은 일반적으로 전역 제약사항
        return "explanation"  # 기본적으로 설명에 적용
    elif "calculation" in id_lower or "계산" in id_lower:
        return "reasoning"  # 계산은 추론과 관련
    elif "table" in id_lower or "chart" in id_lower:
        return "explanation"  # 표/차트는 설명과 관련
    else:
        return "explanation"  # 기본값


def fix_constraint_query_types(dry_run=False):
    """Constraint 노드의 query_type 수정."""
    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME") or os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, username, password]):
        print("❌ Neo4j 접속 정보가 설정되지 않았습니다.")
        sys.exit(1)

    print(f"🔗 Neo4j 연결 중: {uri}\n")
    driver = GraphDatabase.driver(uri, auth=(username, password))

    try:
        with driver.session() as session:
            print("=" * 70)
            if dry_run:
                print("🔍 DRY RUN: 변경사항 미리보기 (실제로 적용하지 않음)")
            else:
                print("🔧 Constraint 노드 query_type 수정")
            print("=" * 70)

            # NULL query_type인 노드 조회
            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IS NULL
                RETURN c.id as id, elementId(c) as element_id
            """)

            nodes = list(result)
            print(f"\n수정할 노드: {len(nodes)}개\n")

            if not nodes:
                print("✅ 모든 Constraint 노드에 이미 query_type이 설정되어 있습니다!")
                return

            # query_type별 카운트
            type_counts = {}
            updates = []

            for node in nodes:
                node_id = node["id"]
                element_id = node["element_id"]

                # query_type 추론
                query_type = infer_query_type(node_id)

                # 카운트 업데이트
                type_counts[query_type] = type_counts.get(query_type, 0) + 1

                updates.append(
                    {
                        "id": node_id or "NULL",
                        "element_id": element_id,
                        "query_type": query_type,
                    }
                )

                print(f"  [{query_type:15}] ID: {node_id or 'NULL'}")

            # 요약 출력
            print(f"\n{'=' * 70}")
            print("📊 변경 요약")
            print("=" * 70)
            for qt, count in sorted(type_counts.items()):
                print(f"  {qt}: {count}개")

            if dry_run:
                print(f"\n{'=' * 70}")
                print("ℹ️  DRY RUN 모드입니다. 실제 변경을 원하시면:")
                print("   python scripts/fix_constraint_query_types.py --apply")
                print("=" * 70)
                return

            # 실제 업데이트 실행
            print(f"\n{'=' * 70}")
            print("🚀 업데이트 실행 중...")
            print("=" * 70)

            for update in updates:
                element_id = update["element_id"]
                query_type = update["query_type"]
                node_id = update["id"]

                # elementId를 사용하여 업데이트
                session.run(
                    """
                    MATCH (c:Constraint)
                    WHERE elementId(c) = $element_id
                    SET c.query_type = $query_type
                """,
                    element_id=element_id,
                    query_type=query_type,
                )

                print(f"  ✓ {node_id} → {query_type}")

            print(f"\n✅ {len(updates)}개 노드 업데이트 완료!")

            # 검증
            print(f"\n{'=' * 70}")
            print("🔍 검증")
            print("=" * 70)

            result = session.run("""
                MATCH (c:Constraint)
                WHERE c.query_type IS NULL
                RETURN count(c) as null_count
            """)
            null_count = result.single()["null_count"]

            if null_count == 0:
                print("✅ 모든 Constraint 노드에 query_type이 설정되었습니다!")
            else:
                print(f"⚠️  여전히 {null_count}개의 노드에 NULL query_type이 있습니다.")

            # query_type별 분포 확인
            result = session.run("""
                MATCH (c:Constraint)
                RETURN c.query_type as qt, count(*) as cnt
                ORDER BY cnt DESC
            """)

            print("\n현재 query_type 분포:")
            for record in result:
                qt = record["qt"] or "NULL"
                cnt = record["cnt"]
                print(f"  - {qt}: {cnt}개")

    finally:
        driver.close()


if __name__ == "__main__":
    import sys

    # 기본값은 DRY RUN
    dry_run = True
    if len(sys.argv) > 1 and sys.argv[1] == "--apply":
        dry_run = False

    fix_constraint_query_types(dry_run=dry_run)
