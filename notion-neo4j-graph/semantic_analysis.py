"""Semantic Analysis module."""

import logging
import os
import re
import sys
from collections import Counter as CounterClass
from typing import Dict, List

from dotenv import load_dotenv
from neo4j import GraphDatabase

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("SemanticAnalysis")

load_dotenv()


class TextProcessor:
    """텍스트 전처리 및 키워드 추출."""

    # 불용어 목록 (한국어/영어)
    STOPWORDS = {
        # 한국어
        "이",
        "그",
        "저",
        "것",
        "수",
        "등",
        "를",
        "을",
        "은",
        "는",
        "가",
        "이",
        "도",
        "에",
        "의",
        "로",
        "한",
        "하다",
        "있다",
        "없다",
        "되다",
        "않다",
        "같다",
        "해서",
        "있는",
        "하는",
        "및",
        "또는",
        "합니다",
        "입니다",
        "있는",
        "없는",
        "대한",
        "위해",
        "통해",
        "따라",
        "경우",
        "때문",
        # 영어
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "and",
        "or",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "but",
        "if",
        "so",
        "not",
        "no",
        "can",
        "could",
        "will",
        "would",
        "should",
        "may",
        "might",
        "must",
        "this",
        "that",
        "it",
        "they",
        "we",
        "you",
        "he",
        "she",
        "what",
        "which",
        "who",
        "whom",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "http",
        "https",
        "www",
        "com",
        "org",
        "net",
    }

    @staticmethod
    def normalize(text: str) -> str:
        """텍스트 정규화: 소문자 변환, 특수문자 제거."""
        # URL 제거
        text = re.sub(r"https?://\S+|www\.\S+", "", text)
        # 특수문자 및 숫자 제거 (한글, 영문, 공백만 유지)
        text = re.sub(r"[^가-힣a-zA-Z\s]", " ", text)
        return text.lower().strip()

    @classmethod
    def extract_keywords(cls, text: str, top_n: int = 5) -> List[str]:
        """텍스트에서 상위 키워드 추출."""
        normalized = cls.normalize(text)
        words = normalized.split()

        # 불용어 필터링 및 길이 제한 (2글자 이상)
        valid_words = [w for w in words if w not in cls.STOPWORDS and len(w) >= 2]

        # 빈도 분석
        counter = CounterClass(valid_words)
        return [word for word, _ in counter.most_common(top_n)]


class SemanticAnalyzer:
    """Neo4j 데이터 의미 분석기."""

    BATCH_SIZE = 500

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

    def analyze_blocks(self):
        """블록 데이터를 가져와 키워드 분석 후 Topic 연결."""
        logger.info("🔍 블록 데이터 분석 시작...")

        try:
            with self.driver.session() as session:
                # 1. 모든 블록의 콘텐츠 가져오기
                result = session.run("""
                    MATCH (b:Block)
                    WHERE b.content IS NOT NULL AND b.content <> ''
                    RETURN b.id AS id, b.content AS content
                """)

                blocks = list(result)
                logger.info(f"   - 분석 대상 블록: {len(blocks)}개")

                topic_mappings = []
                all_keywords = CounterClass()

                # 2. Python에서 키워드 추출 (부하 분산)
                for record in blocks:
                    keywords = TextProcessor.extract_keywords(record["content"])
                    if keywords:
                        all_keywords.update(keywords)
                        topic_mappings.extend(
                            {"block_id": record["id"], "topic": kw} for kw in keywords
                        )

                logger.info(f"   - 추출된 고유 키워드: {len(all_keywords)}개")

                # 3. 상위 키워드만 필터링 (노이즈 제거)
                # 전체 문서에서 최소 2회 이상 등장한 키워드만 Topic으로 생성
                valid_topics = {kw for kw, count in all_keywords.items() if count >= 2}

                final_mappings = [
                    m for m in topic_mappings if m["topic"] in valid_topics
                ]

                logger.info(
                    f"   - 필터링 후 매핑: {len(final_mappings)}개 (최소 빈도 2회 이상)"
                )

                # 4. 배치 단위로 Neo4j 업데이트
                self._batch_update_topics(session, final_mappings)

        except Exception as e:
            logger.error(f"❌ 분석 중 오류 발생: {e}")
            raise

    def _batch_update_topics(self, session, mappings: List[Dict]):
        """배치 단위로 Topic 노드 생성 및 연결."""
        total = len(mappings)
        for i in range(0, total, self.BATCH_SIZE):
            batch = mappings[i : i + self.BATCH_SIZE]

            # Topic 노드 생성 및 관계 설정 (Optimized Cypher)
            query = """
            UNWIND $batch AS item
            MERGE (t:Topic {name: item.topic})
            WITH t, item
            MATCH (b:Block {id: item.block_id})
            MERGE (b)-[:DISCUSSES]->(t)
            """

            session.run(query, batch=batch)
            logger.info(
                f"   - 배치 처리 중... ({min(i + self.BATCH_SIZE, total)}/{total})"
            )

        logger.info("✅ Topic 생성 및 연결 완료")


def main():
    """의미 분석 메인 실행 함수."""
    analyzer = SemanticAnalyzer()
    try:
        analyzer.analyze_blocks()
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
