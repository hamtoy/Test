"""Phase 2+: Example 균형 맞추기

현재 Example 분포를 확인하고, 부족한 카테고리에 Example을 추가하여
모든 카테고리가 5개씩 되도록 균형을 맞춥니다.
"""

import os
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()


class ExampleBalancer:
    """Example 균형을 맞추는 클래스"""

    def __init__(self) -> None:
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        if uri is None or user is None or password is None:
            raise ValueError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD must be set")

        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

        # 목표: 모든 카테고리 5개씩
        self.target_count: int = 5

    def get_current_distribution(self) -> Dict[str, int]:
        """현재 카테고리별 Example 분포 확인"""
        with self.driver.session() as session:  # type: Session
            result = session.run(
                """
                MATCH (e:Example)
                WHERE e.id STARTS WITH 'example_feedback_'
                RETURN e.source AS category, count(e) AS count
                ORDER BY count ASC
                """
            )
            return {record["category"]: int(record["count"]) for record in result}

    def add_examples_for_category(self, category: str, needed: int) -> int:
        """특정 카테고리에 Example 추가"""
        with self.driver.session() as session:  # type: Session
            # 1. 이미 사용된 line_number 확인
            result = session.run(
                """
                MATCH (e:Example {source: $category})
                WHERE e.id STARTS WITH 'example_feedback_'
                RETURN e.id AS id
                """,
                category=category,
            )
            used_line_numbers = set()
            for record in result:
                line_num = record["id"].replace("example_feedback_", "")
                used_line_numbers.add(int(line_num))

            # 2. 새로운 Example 후보 추출 (이미 사용된 것 제외)
            result = session.run(
                """
                MATCH (fc:FeedbackCategory {name: $category})<-[:CATEGORIZED_AS]-(f:Feedback)
                WHERE size(f.content) > 30 AND size(f.content) < 200
                    AND (f.content CONTAINS '수정' OR f.content CONTAINS '변경' 
                         OR f.content CONTAINS '→' OR f.content CONTAINS '오류'
                         OR f.content CONTAINS '사실' OR f.content CONTAINS '형식')
                RETURN f.line_number AS line_number, f.content AS content
                ORDER BY size(f.content) ASC
                LIMIT $limit
                """,
                category=category,
                limit=needed * 3,  # 여유있게 가져오기
            )

            examples: List[Dict[str, object]] = [
                {
                    "line_number": int(record["line_number"]),
                    "content": str(record["content"]),
                }
                for record in result
                if int(record["line_number"]) not in used_line_numbers
            ][:needed]

            if not examples:
                print(f"⚠️  {category}: 추가할 피드백이 없습니다")
                return 0

            # 3. Rule ID 조회
            rule_result = session.run(
                """
                MATCH (fc:FeedbackCategory {name: $category})-[:GENERATED_RULE]->(r:Rule)
                RETURN r.id AS rule_id
                """,
                category=category,
            )

            rule_record = rule_result.single()
            if not rule_record:
                print(f"⚠️  {category}: 연결된 Rule이 없습니다")
                return 0

            rule_id = str(rule_record["rule_id"])

            # 4. Example 노드 생성 및 Rule 연결
            created_count = 0
            for example in examples:
                example_id = f"example_feedback_{example['line_number']}"
                example_text = example["content"]

                # Example 노드 생성
                session.run(
                    """
                    MERGE (e:Example {id: $example_id})
                    SET e.text = $example_text,
                        e.type = 'feedback',
                        e.source = $category,
                        e.created_at = datetime()
                    """,
                    example_id=example_id,
                    example_text=example_text,
                    category=category,
                )

                # Rule과 DEMONSTRATES 관계 생성
                session.run(
                    """
                    MATCH (e:Example {id: $example_id})
                    MATCH (r:Rule {id: $rule_id})
                    MERGE (e)-[:DEMONSTRATES]->(r)
                    """,
                    example_id=example_id,
                    rule_id=rule_id,
                )

                created_count += 1

            print(
                f"✅ {category}: +{created_count}개 추가 (총 {used_line_numbers.__len__() + created_count}개)"
            )
            return created_count

    def balance(self) -> None:
        """Example 균형 맞추기"""
        print("=== Example 균형 맞추기 ===\n")

        # 현재 분포 확인
        current = self.get_current_distribution()
        print("현재 분포:")
        for category, count in sorted(current.items(), key=lambda x: x[1]):
            print(f"  {category}: {count}개")

        print(f"\n목표: 모든 카테고리 {self.target_count}개씩\n")

        # 부족한 카테고리에 추가
        total_added = 0
        for category, count in current.items():
            needed = self.target_count - count
            if needed > 0:
                added = self.add_examples_for_category(category, needed)
                total_added += added

        if total_added == 0:
            print("\n✅ 이미 균형이 맞춰져 있습니다!")
        else:
            print(f"\n✅ 총 {total_added}개 Example 추가 완료")

        # 최종 분포 확인
        final = self.get_current_distribution()
        print("\n최종 분포:")
        for category, count in sorted(final.items()):
            print(f"  {category}: {count}개")

        total = sum(final.values())
        print(f"\n총 Example: {total}개")

    def close(self) -> None:
        """드라이버 종료"""
        self.driver.close()


if __name__ == "__main__":
    balancer = ExampleBalancer()
    try:
        balancer.balance()
    finally:
        balancer.close()
