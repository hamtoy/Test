"""Compare Documents module."""

import logging
import os
import sys
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("DocumentComparator")

load_dotenv()


class DocumentComparator:
    """문서 간 유사성 및 공통점 분석."""

    def __init__(self):
        """초기화: 환경 변수 검증 및 Neo4j 드라이버 설정."""
        self._validate_env()
        self.driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
        )

    def _validate_env(self):
        """환경 변수 검증."""
        required = ["NEO4J_URI", "NEO4J_PASSWORD"]
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            logger.error(f"❌ 필수 환경 변수 누락: {', '.join(missing)}")
            sys.exit(1)

    def close(self):
        """Neo4j 드라이버 종료."""
        self.driver.close()

    @contextmanager
    def session_context(self):
        """Neo4j 세션 관리를 위한 컨텍스트 매니저."""
        session = self.driver.session()
        try:
            yield session
        finally:
            session.close()

    def find_common_content(self):
        """문서 간 공통적으로 등장하는 콘텐츠 탐색."""
        logger.info("🔍 문서 간 공통 콘텐츠 분석 시작...")

        query = """
        MATCH (p1:Page)-[:HAS_BLOCK]->(b1:Block)
        MATCH (p2:Page)-[:HAS_BLOCK]->(b2:Block)
        WHERE p1.id < p2.id  // 중복 쌍 제거 및 자기 자신 비교 제외
          AND b1.content = b2.content
          AND b1.content IS NOT NULL 
          AND b1.content <> ''
          AND size(b1.content) > 10  // 너무 짧은 콘텐츠 제외
        
        WITH b1.content AS content, collect(DISTINCT p1.title) + collect(DISTINCT p2.title) AS pages, count(*) as match_count
        WHERE size(pages) > 1
        
        RETURN content, pages, size(pages) as page_count
        ORDER BY page_count DESC, size(content) DESC
        LIMIT 10
        """

        try:
            with self.session_context() as session:
                result = session.run(query)
                records = list(result)

                if not records:
                    logger.info("ℹ️  공통 콘텐츠가 발견되지 않았습니다.")
                    return

                print(f"\n📊 공통 콘텐츠 분석 결과 (Top {len(records)}):")
                print("=" * 60)

                for idx, record in enumerate(records, 1):
                    content = record["content"]
                    # 긴 콘텐츠는 잘라서 표시
                    snippet = content[:50] + "..." if len(content) > 50 else content
                    pages = list(set(record["pages"]))  # 중복 제거

                    print(f'{idx}. "{snippet}"')
                    print(f"   - 등장 횟수: {len(pages)}개 페이지")
                    print(f"   - 출처: {', '.join(pages)}")
                    print("-" * 60)

        except Exception as e:
            logger.error(f"❌ 분석 중 오류 발생: {e}")
            raise

    def compare_pages_by_topics(self):
        """페이지 간 공유하는 토픽 분석."""
        logger.info("🔍 페이지 간 토픽 유사도 분석 시작...")

        query = """
        MATCH (p1:Page)<-[:MENTIONS|HAS_BLOCK]-(:Block)-[:DISCUSSES]->(t:Topic)<-[:DISCUSSES]-(:Block)-[:MENTIONS|HAS_BLOCK]->(p2:Page)
        WHERE p1.id < p2.id
        
        WITH p1, p2, collect(DISTINCT t.name) as shared_topics, count(DISTINCT t) as topic_count
        WHERE topic_count > 0
        
        RETURN p1.title as page1, p2.title as page2, shared_topics, topic_count
        ORDER BY topic_count DESC
        LIMIT 5
        """

        try:
            with self.session_context() as session:
                result = session.run(query)
                records = list(result)

                if not records:
                    logger.info("ℹ️  공유하는 토픽이 없습니다.")
                    return

                print(f"\n🤝 페이지 간 토픽 유사도 (Top {len(records)}):")
                print("=" * 60)

                for record in records:
                    print(f"[{record['page1']}] ↔ [{record['page2']}]")
                    print(
                        f"   - 공유 토픽 ({record['topic_count']}개): {', '.join(record['shared_topics'][:5])}"
                        + ("..." if len(record["shared_topics"]) > 5 else "")
                    )
                    print("-" * 60)

        except Exception as e:
            logger.error(f"❌ 토픽 분석 중 오류 발생: {e}")


def main():
    """문서 비교 메인 실행 함수."""
    comparator = DocumentComparator()
    try:
        comparator.find_common_content()
        comparator.compare_pages_by_topics()
    finally:
        comparator.close()


if __name__ == "__main__":
    main()
