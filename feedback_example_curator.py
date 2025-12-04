"""Phase 2: 수동 샘플링 유틸리티

피드백에서 Example로 변환할 후보를 추출하고 검토하는 도구
"""

import os
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


class ExampleCandidateExtractor:
    """피드백에서 Example 후보 추출"""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def extract_candidates(self, category: str, limit: int = 20) -> List[Dict]:
        """특정 카테고리에서 Example 후보 추출

        선택 기준:
        - "수정", "변경", "->", "삭제" 등 구체적인 지시사항 포함
        - 문장 길이가 적당함 (너무 짧거나 길지 않음)
        """
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (f:Feedback)-[:CATEGORIZED_AS]->(fc:FeedbackCategory {name: $category})
                WHERE (f.content CONTAINS '수정' OR
                       f.content CONTAINS '변경' OR
                       f.content CONTAINS '->' OR
                       f.content CONTAINS '삭제' OR
                       f.content CONTAINS '추가' OR
                       f.content CONTAINS '필요')
                  AND size(f.content) > 30
                  AND size(f.content) < 300
                RETURN f.line_number AS line_number,
                       f.content AS content
                ORDER BY rand()
                LIMIT $limit
                """,
                category=category,
                limit=limit,
            )

            candidates = [
                {"line_number": record["line_number"], "content": record["content"]}
                for record in result
            ]

            return candidates

    def create_examples_from_approved(
        self, approved_line_numbers: List[int], category: str
    ) -> Dict:
        """승인된 피드백을 Example로 변환

        Args:
            approved_line_numbers: 승인된 피드백의 line_number 리스트
            category: 카테고리 이름
        """
        with self.driver.session() as session:
            # 해당 카테고리의 Rule 찾기
            rule_result = session.run(
                """
                MATCH (r:Rule)
                WHERE r.category = $category
                RETURN r.id AS rule_id
                LIMIT 1
                """,
                category=category,
            )
            rule_record = rule_result.single()
            if not rule_record:
                return {
                    "error": f"Rule not found for category: {category}",
                    "created": 0,
                }

            rule_id = rule_record["rule_id"]

            # Example 생성
            created_ids = []
            for line_number in approved_line_numbers:
                result = session.run(
                    """
                    MATCH (f:Feedback {line_number: $line_number})
                    MATCH (r:Rule {id: $rule_id})
                    CREATE (e:Example {
                        id: 'example_feedback_' + toString(f.line_number),
                        content: f.content,
                        type: 'anti_pattern',
                        source: 'reviewer_feedback',
                        line_number: f.line_number,
                        created_at: datetime()
                    })
                    CREATE (e)-[:DEMONSTRATES]->(r)
                    CREATE (f)-[:CONVERTED_TO]->(e)
                    RETURN e.id AS example_id
                    """,
                    line_number=line_number,
                    rule_id=rule_id,
                )
                record = result.single()
                if record:
                    created_ids.append(record["example_id"])

            return {"created": len(created_ids), "example_ids": created_ids}


def interactive_review(category: str, limit: int = 10):
    """대화형 검토 인터페이스"""
    extractor = ExampleCandidateExtractor(
        os.getenv("NEO4J_URI"), os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")
    )

    try:
        print(f"\n{'=' * 70}")
        print(f"피드백 → Example 변환 후보 검토 (카테고리: {category})")
        print(f"{'=' * 70}\n")

        candidates = extractor.extract_candidates(category, limit)

        if not candidates:
            print("⚠️  해당 카테고리에서 적합한 후보를 찾지 못했습니다.")
            return

        print(f"총 {len(candidates)}개의 후보를 추출했습니다.\n")

        approved = []
        for i, candidate in enumerate(candidates, 1):
            print(f"\n[{i}/{len(candidates)}] Line {candidate['line_number']}")
            print("-" * 70)
            print(candidate["content"])
            print("-" * 70)

            response = input("Example로 추가? (y/n/q-종료): ").strip().lower()

            if response == "q":
                break
            elif response == "y":
                approved.append(candidate["line_number"])
                print("✅ 승인")
            else:
                print("❌ 제외")

        if approved:
            print(f"\n총 {len(approved)}개를 Example로 변환합니다...")
            result = extractor.create_examples_from_approved(approved, category)

            if "error" in result:
                print(f"❌ 오류: {result['error']}")
            else:
                print(f"✅ {result['created']}개의 Example 생성 완료!")
                print("\n생성된 Example ID:")
                for eid in result["example_ids"]:
                    print(f"  • {eid}")
        else:
            print("\n승인된 항목이 없습니다.")

    finally:
        extractor.close()


if __name__ == "__main__":
    # 사용 예시
    print("\n[Phase 2] Example 후보 수동 검토")
    print("\n카테고리 목록:")
    categories = [
        "형식 오류",
        "문법/맞춤법",
        "반복 표현",
        "시의성 표현",
        "추론 문제",
        "인용 형식",
        "사실성 오류",
        "용어 통일",
    ]

    for i, cat in enumerate(categories, 1):
        print(f"  {i}. {cat}")

    choice = input("\n검토할 카테고리 번호 (1-8): ").strip()

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(categories):
            interactive_review(categories[idx], limit=10)
        else:
            print("❌ 잘못된 번호입니다.")
    except ValueError:
        print("❌ 숫자를 입력해주세요.")
