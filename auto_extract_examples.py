"""Phase 2: 피드백을 Example 노드로 자동 변환

각 카테고리별로 조건에 맞는 피드백을 추출하여 Example 노드를 생성하고
해당 카테고리의 Rule과 DEMONSTRATES 관계를 생성합니다.
"""

import os
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()


class ExampleExtractor:
    """피드백을 Example 노드로 변환하는 클래스"""

    def __init__(self) -> None:
        uri = os.getenv("NEO4J_URI")
        user = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        if uri is None or user is None or password is None:
            raise ValueError("NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD must be set")

        self.driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

        # 카테고리별 추출 개수
        self.category_limits: Dict[str, int] = {
            "사실성 오류": 5,
            "형식 오류": 5,
            "문법/맞춤법": 3,
            "시의성 표현": 3,
            "반복 표현": 3,
            "인용 형식": 3,
            "추론 문제": 3,
            "용어 통일": 3,
        }

    def extract_examples_for_category(self, category: str, limit: int) -> int:
        """카테고리별로 Example 후보를 추출하고 Example 노드로 변환"""
        with self.driver.session() as session:  # type: Session
            # 1. 조건에 맞는 피드백 추출
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
                limit=limit,
            )

            examples: List[Dict[str, str]] = [
                {
                    "line_number": str(record["line_number"]),
                    "content": str(record["content"]),
                }
                for record in result
            ]

            if not examples:
                print(f"⚠️  {category}: 조건에 맞는 피드백이 없습니다")
                return 0

            # 2. 해당 카테고리의 Rule ID 조회
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

            # 3. Example 노드 생성 및 Rule 연결
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

            print(f"✅ {category}: {created_count}개 Example 생성")
            return created_count

    def run(self) -> None:
        """모든 카테고리에 대해 Example 추출 실행"""
        print("=== Phase 2: 피드백 → Example 변환 시작 ===\n")

        total_created = 0
        for category, limit in self.category_limits.items():
            count = self.extract_examples_for_category(category, limit)
            total_created += count

        print(f"\n=== 완료: 총 {total_created}개 Example 생성 ===")

        # 검증: 생성된 Example 통계
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Example)
                WHERE e.id STARTS WITH 'example_feedback_'
                RETURN count(e) AS total
                """
            )
            total_row = result.single()
            total = int(total_row["total"]) if total_row else 0
            print(f"\nNeo4j 검증: Example 노드 {total}개 확인")

            # Rule별 Example 분포
            result = session.run(
                """
                MATCH (r:Rule)<-[:DEMONSTRATES]-(e:Example)
                WHERE r.source = 'feedback_analysis'
                RETURN r.text AS rule, count(e) AS example_count
                ORDER BY example_count DESC
                """
            )
            print("\n카테고리별 Example 분포:")
            for record in result:
                print(f"  - {record['rule'][:30]}...: {record['example_count']}개")

    def close(self) -> None:
        """드라이버 종료"""
        self.driver.close()


if __name__ == "__main__":
    extractor = ExampleExtractor()
    try:
        extractor.run()
    finally:
        extractor.close()
