"""Neo4j 인덱스 최적화 효과 검증 스크립트.

인덱스 사용 여부와 캐시 워밍업 효과를 확인합니다.
"""

import os
import sys
import time

from neo4j import GraphDatabase


def verify_optimization():
    """Neo4j 최적화 효과 검증."""
    # 환경 변수에서 Neo4j 접속 정보 가져오기
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
            print("📊 1. 인덱스 사용 확인 (PROFILE 분석)")
            print("=" * 70)

            # PROFILE로 쿼리 실행
            query = "MATCH (c:Constraint {query_type: 'explanation'}) RETURN c LIMIT 1"
            print(f"\n쿼리: {query}\n")

            result = session.run(f"PROFILE {query}")

            # 프로파일 정보 추출
            profile = result.consume().profile

            def print_profile(plan, indent=0):
                """재귀적으로 프로파일 정보 출력."""
                prefix = "  " * indent
                operator = plan.get("operatorType", "Unknown")
                db_hits = plan.get("dbHits", 0)
                rows = plan.get("rows", 0)

                print(f"{prefix}📍 {operator}")
                print(f"{prefix}   DbHits: {db_hits:,} | Rows: {rows:,}")

                # 인덱스 사용 확인
                if "index" in operator.lower():
                    print(f"{prefix}   ✅ 인덱스 사용됨!")
                    if "identifiers" in plan:
                        print(f"{prefix}   변수: {plan['identifiers']}")
                    if "arguments" in plan:
                        args = plan["arguments"]
                        if "indexName" in args:
                            print(f"{prefix}   인덱스명: {args['indexName']}")

                # 자식 노드 재귀 처리
                if "children" in plan:
                    for child in plan["children"]:
                        print_profile(child, indent + 1)

            if profile:
                print_profile(profile)

                # 총 DbHits 계산
                def count_db_hits(plan):
                    total = plan.get("dbHits", 0)
                    if "children" in plan:
                        for child in plan["children"]:
                            total += count_db_hits(child)
                    return total

                total_hits = count_db_hits(profile)
                print(f"\n📈 총 DbHits: {total_hits:,}")

            print("\n" + "=" * 70)
            print("🔥 2. 캐시 워밍업 효과 측정")
            print("=" * 70)

            # 첫 번째 실행 (콜드 스타트)
            query = "MATCH (c:Constraint) RETURN c.query_type, count(*) as cnt"
            print(f"\n쿼리: {query}")
            print("\n[콜드 스타트] 첫 번째 실행...")

            start = time.time()
            result = session.run(query)
            records = list(result)
            cold_time = time.time() - start

            print(f"⏱️  실행 시간: {cold_time * 1000:.2f}ms")
            print(f"📊 결과 레코드: {len(records)}개")
            for record in records:
                qt = record["c.query_type"] or "None"
                cnt = record["cnt"]
                print(f"   - {qt}: {cnt}개")

            # 두 번째 실행 (캐시 적용)
            print("\n[캐시 적중] 두 번째 실행...")
            start = time.time()
            result = session.run(query)
            list(result)
            warm_time = time.time() - start

            print(f"⏱️  실행 시간: {warm_time * 1000:.2f}ms")

            # 세 번째 실행 (캐시 완전 적중)
            print("\n[캐시 완전 적중] 세 번째 실행...")
            start = time.time()
            result = session.run(query)
            list(result)
            hot_time = time.time() - start

            print(f"⏱️  실행 시간: {hot_time * 1000:.2f}ms")

            # 개선율 계산
            improvement_warm = (
                ((cold_time - warm_time) / cold_time * 100) if cold_time > 0 else 0
            )
            improvement_hot = (
                ((cold_time - hot_time) / cold_time * 100) if cold_time > 0 else 0
            )

            print("\n📈 개선율:")
            print(f"   콜드 → 웜: {improvement_warm:.1f}% 빨라짐")
            print(f"   콜드 → 핫: {improvement_hot:.1f}% 빨라짐")

            print("\n" + "=" * 70)
            print("📊 3. query_type 별 성능 측정")
            print("=" * 70)

            query_types = [
                "explanation",
                "reasoning",
                "summary",
                "target_short",
                "target_long",
            ]

            for qt in query_types:
                query = f"MATCH (c:Constraint {{query_type: '{qt}'}}) RETURN count(c) as cnt"

                start = time.time()
                result = session.run(query)
                record = result.single()
                elapsed = time.time() - start

                count = record["cnt"] if record else 0
                print(f"\n{qt}:")
                print(f"   노드 수: {count}개")
                print(f"   실행 시간: {elapsed * 1000:.2f}ms")

            print("\n" + "=" * 70)
            print("✅ 검증 완료!")
            print("=" * 70)

            print("\n💡 권장 사항:")
            if total_hits < 100:
                print("  ✅ 인덱스가 효과적으로 작동하고 있습니다 (DbHits < 100)")
            else:
                print("  ⚠️  DbHits가 높습니다. 추가 최적화를 고려하세요.")

            if improvement_hot > 30:
                print("  ✅ 캐시 워밍업이 효과적입니다 (30% 이상 개선)")
            else:
                print("  ℹ️  캐시 효과가 제한적입니다. 쿼리 패턴을 검토하세요.")

    finally:
        driver.close()


if __name__ == "__main__":
    verify_optimization()
