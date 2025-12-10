"""Notion에서 추출한 Block 콘텐츠를 기반으로 Topic 노드를 만들고.

블록과 토픽을 매핑하는 스크립트.

개선 사항:
- 환경 변수 검증 (NEO4J_URI/USER/PASSWORD 누락 시 친절한 오류)
- 텍스트 정규화(소문자화, 구두점 제거)와 간단한 불용어 필터
- 빈도 기준으로 상위 키워드만 Topic으로 생성
- 파이썬에서 토큰-블록 매핑을 계산해 Neo4j에서의 전체 조인(카티전 곱) 회피
- 관계 생성은 MERGE로 중복 없이 배치 처리
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
import sys
from collections import Counter
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from neo4j import Driver, GraphDatabase
from neo4j.exceptions import Neo4jError

from src.config.utils import require_env

# --------------------
# 설정
# --------------------

MIN_WORD_LEN = 3
MIN_FREQ = 5
TOP_K = 30
REL_BATCH_SIZE = 500

STOPWORDS = {
    # English
    "the",
    "and",
    "for",
    "are",
    "but",
    "not",
    "you",
    "your",
    "with",
    "this",
    "that",
    "from",
    "have",
    "has",
    "was",
    "were",
    "will",
    "would",
    "can",
    "could",
    "should",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "at",
    "as",
    "is",
    "it",
    "by",
    "be",
    "or",
    "if",
    "we",
    "our",
    # Korean (간단 예시)
    "그리고",
    "하지만",
    "그러나",
    "또한",
    "입니다",
    "있습니다",
    "하는",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9가-힣']+")

# Ensure log directory exists to avoid import-time failures in test/CI.
LOG_PATH = Path("logs/semantic_analysis.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# --------------------
# 유틸리티
# --------------------


def tokenize(text: str) -> list[str]:
    """간단한 토큰화: 소문자화, 구두점 제거, 불용어/길이 필터."""
    tokens = []
    for raw in TOKEN_PATTERN.findall(text.lower()):
        if len(raw) < MIN_WORD_LEN:
            continue
        if raw in STOPWORDS:
            continue
        tokens.append(raw)
    return tokens


def count_keywords(contents: Iterable[str]) -> Counter[str]:
    """Count keyword frequencies from text contents.

    Args:
        contents: Iterable of text strings to analyze.

    Returns:
        Counter of keywords that meet minimum frequency threshold.
    """
    counter: Counter[str] = Counter()
    for text in contents:
        counter.update(tokenize(text))
    # 빈도 필터
    for word in list(counter.keys()):
        if counter[word] < MIN_FREQ:
            del counter[word]
    return counter


def create_topics(driver: Driver, keywords: list[tuple[str, int]]) -> None:
    """Create Topic nodes in Neo4j from keyword frequencies.

    Args:
        driver: Neo4j driver instance.
        keywords: List of (keyword, frequency) tuples.
    """

    def _tx(tx: Any, items: list[tuple[str, int]]) -> None:
        tx.run(
            """
            UNWIND $topics AS t
            MERGE (topic:Topic {name: t.word})
            SET topic.frequency = t.freq
            """,
            topics=[{"word": w, "freq": f} for w, f in items],
        )

    if not keywords:
        logger.info("생성할 토픽이 없습니다.")
        return

    with driver.session() as session:
        session.execute_write(_tx, keywords)
    logger.info("Topic %d개 생성/업데이트 완료", len(keywords))


def link_blocks_to_topics(
    driver: Driver,
    blocks: list[dict[str, Any]],
    topics: list[tuple[str, int]],
) -> None:
    """Create TAGGED_WITH relationships between blocks and topics.

    Args:
        driver: Neo4j driver instance.
        blocks: List of block dictionaries with id and content.
        topics: List of (keyword, frequency) tuples.
    """
    topic_set = {w for w, _ in topics}
    links: list[dict[str, str]] = []

    def flush(batch: list[dict[str, str]]) -> None:
        """Flush a batch of block-topic relationships to the database."""
        if not batch:
            return
        with driver.session() as session:
            session.execute_write(
                lambda tx, rows: tx.run(
                    """
                    UNWIND $links AS link
                    MATCH (b:Block {id: link.block_id})
                    MATCH (t:Topic {name: link.topic})
                    MERGE (b)-[:TAGGED_WITH]->(t)
                    """,
                    links=rows,
                ),
                batch,
            )

    for block in blocks:
        content = block.get("content") or ""
        block_id = block.get("id")
        if not block_id or not content:
            continue
        tokens = set(tokenize(content))
        matched = tokens.intersection(topic_set)
        links.extend({"block_id": block_id, "topic": topic} for topic in matched)
        if len(links) >= REL_BATCH_SIZE:
            flush(links)
            links = []

    flush(links)
    logger.info("Block-Topic 관계 생성 완료")


def fetch_blocks(driver: Driver) -> list[dict[str, Any]]:
    """Fetch blocks with content from Neo4j.

    Args:
        driver: Neo4j driver instance.

    Returns:
        List of block dictionaries with id and content.
    """
    with driver.session() as session:
        result = session.run(
            """
            MATCH (b:Block)
            WHERE coalesce(b.content, '') <> '' AND size(b.content) > 10
            RETURN b.id AS id, b.content AS content
            """,
        )
        return [dict(record) for record in result]


# --------------------
# 메인 흐름
# --------------------


def main() -> None:
    """Entry point for semantic topic extraction script."""
    load_dotenv()

    try:
        config = {
            "uri": require_env("NEO4J_URI"),
            "user": require_env("NEO4J_USER"),
            "password": require_env("NEO4J_PASSWORD"),
        }
    except OSError as e:
        logger.error(str(e))
        sys.exit(1)

    try:
        driver = GraphDatabase.driver(
            config["uri"],
            auth=(config["user"], config["password"]),
        )
    except Neo4jError as e:
        logger.error("Neo4j 연결 실패: %s", e)
        sys.exit(1)

    try:
        blocks = fetch_blocks(driver)
        if not blocks:
            logger.info("처리할 Block이 없습니다.")
            return

        contents = [b["content"] for b in blocks if b.get("content")]
        keyword_counter = count_keywords(contents)
        keywords = keyword_counter.most_common(TOP_K)

        logger.info("Top %d 키워드: %s", len(keywords), keywords[:10])

        create_topics(driver, keywords)
        link_blocks_to_topics(driver, blocks, keywords)

    except Neo4jError as e:
        logger.error("Neo4j 오류 발생: %s", e, exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.error("예상치 못한 오류: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        driver.close()
        logger.info("Neo4j 연결 종료")


if __name__ == "__main__":
    main()
