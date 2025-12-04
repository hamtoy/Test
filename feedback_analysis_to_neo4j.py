"""피드백 데이터를 분석하여 Neo4j에 저장하는 스크립트

경향성 분석을 위해:
- Feedback 노드: 각 피드백 라인
- FeedbackCategory 노드: 피드백 유형 (문법, 사실성, 형식 등)
- 관계: (Feedback)-[:CATEGORIZED_AS]->(FeedbackCategory)
"""

import os
import re
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase

# 환경 변수 로드
load_dotenv()

# Neo4j 연결 설정
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")


class FeedbackAnalyzer:
    """피드백 데이터 분석 및 Neo4j 저장"""

    # 피드백 카테고리 정의
    CATEGORY_PATTERNS = {
        "문법/맞춤법": r"(오타|띄어쓰기|조사|어미|문장 부자연스러움|표현 부자연스러움)",
        "사실성 오류": r"(사실성 오류|이미지에 없는|정보 누락|내용 확인)",
        "형식 오류": r"(목록형 답변|불릿|볼드체|들여쓰기|콜론|공백|문단 구분)",
        "시의성 표현": r"(시의적|시의성|최근|현재|올해|전일|전월|지난달)",
        "반복 표현": r"(반복|중복|동일한 표현)",
        "용어 통일": r"(용어 통일|고유명사|경제 용어|이미지에 있는 그대로)",
        "추론 문제": r"(추론|무리한 추론|이미지에 근거)",
        "인용 형식": r"(인용|언급하고|전하고 있습니다|표현했습니다)",
    }

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def analyze_feedback_line(self, line: str) -> List[str]:
        """피드백 라인에서 카테고리 추출"""
        categories = []
        for category, pattern in self.CATEGORY_PATTERNS.items():
            if re.search(pattern, line):
                categories.append(category)
        return categories

    def parse_feedback_file(self, filepath: str) -> List[Dict]:
        """피드백 파일 파싱"""
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        feedbacks = []
        for i, line in enumerate(lines, 1):
            content = line.strip()
            if content:
                categories = self.analyze_feedback_line(content)
                feedbacks.append(
                    {"line_number": i, "content": content, "categories": categories}
                )

        return feedbacks

    def create_constraints(self):
        """Neo4j 제약조건 생성"""
        with self.driver.session() as session:
            # Feedback 노드 유니크 제약
            session.run(
                """
                CREATE CONSTRAINT feedback_line_unique IF NOT EXISTS
                FOR (f:Feedback) REQUIRE f.line_number IS UNIQUE
                """
            )

            # FeedbackCategory 노드 유니크 제약
            session.run(
                """
                CREATE CONSTRAINT feedback_category_unique IF NOT EXISTS
                FOR (c:FeedbackCategory) REQUIRE c.name IS UNIQUE
                """
            )

    def import_feedbacks(self, feedbacks: List[Dict]):
        """피드백 데이터를 Neo4j에 저장"""
        with self.driver.session() as session:
            # 1. FeedbackCategory 노드 생성
            for category in self.CATEGORY_PATTERNS:
                session.run(
                    """
                    MERGE (c:FeedbackCategory {name: $name})
                    """,
                    name=category,
                )

            # 2. Feedback 노드 및 관계 생성
            for feedback in feedbacks:
                session.run(
                    """
                    MERGE (f:Feedback {line_number: $line_number})
                    SET f.content = $content
                    """,
                    line_number=feedback["line_number"],
                    content=feedback["content"],
                )

                # 카테고리 관계 생성
                for category in feedback["categories"]:
                    session.run(
                        """
                        MATCH (f:Feedback {line_number: $line_number})
                        MATCH (c:FeedbackCategory {name: $category})
                        MERGE (f)-[:CATEGORIZED_AS]->(c)
                        """,
                        line_number=feedback["line_number"],
                        category=category,
                    )

    def get_statistics(self) -> Dict:
        """통계 조회"""
        with self.driver.session() as session:
            # 카테고리별 피드백 개수
            result = session.run(
                """
                MATCH (c:FeedbackCategory)<-[:CATEGORIZED_AS]-(f:Feedback)
                RETURN c.name AS category, count(f) AS count
                ORDER BY count DESC
                """
            )
            stats = {record["category"]: record["count"] for record in result}

            # 전체 피드백 개수
            total = session.run(
                """
                MATCH (f:Feedback)
                RETURN count(f) AS total
                """
            ).single()["total"]

            return {"total_feedbacks": total, "by_category": stats}


def main():
    """메인 실행 함수"""
    analyzer = FeedbackAnalyzer(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        print("피드백 파일 파싱 중...")
        feedbacks = analyzer.parse_feedback_file("blackwater.txt")
        print(f"총 {len(feedbacks)}개의 피드백 라인 파싱 완료")

        print("\nNeo4j 제약조건 생성 중...")
        analyzer.create_constraints()

        print("\n피드백 데이터 임포트 중...")
        analyzer.import_feedbacks(feedbacks)
        print("임포트 완료!")

        print("\n=== 피드백 통계 ===")
        stats = analyzer.get_statistics()
        print(f"전체 피드백: {stats['total_feedbacks']}개")
        print("\n카테고리별 분포:")
        for category, count in sorted(
            stats["by_category"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"  {category}: {count}개")

    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
