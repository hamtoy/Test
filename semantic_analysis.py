"""
Notion에서 추출한 Block 콘텐츠를 기반으로 Topic 노드를 만들고
블록과 토픽을 매핑하는 스크립트.

개선 사항:
- 환경 변수 검증 (NEO4J_URI/USER/PASSWORD 누락 시 친절한 오류)
- 텍스트 정규화(소문자화, 구두점 제거)와 간단한 불용어 필터
- 빈도 기준으로 상위 키워드만 Topic으로 생성
- 파이썬에서 토큰-블록 매핑을 계산해 Neo4j에서의 전체 조인(카티전 곱) 회피
- 관계 생성은 MERGE로 중복 없이 배치 처리
"""

from __future__ import annotations

import os
import sys
import json
import logging
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

# --------------------
# 설정
# --------------------

MIN_WORD_LEN = 3
MIN_FREQ = 5
TOP_K = 30
REL_BATCH_SIZE = 500

STOPWORDS = {
    # English
    "the", "and", "for", "are", "but", "not", "you", "your", "with",
    "this", "that", "from", "have", "has", "was", "were", "will", "would",
    "can", "could", "should", "a", "an", "of", "to", "in", "on", "at",
    "as", "is", "it", "by", "be", "or", "if", "we", "our",
    # Korean (간단 예시)
    "그리고", "하지만", "그러나", "또한", "입니다", "있습니다", "하는",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9가-힣']+")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("semantic_analysis.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# --------------------
# 유틸리티
# --------------------

def require_env(var: str) -> str:
    value = os.getenv(var)
    if not value:
        raise EnvironmentError(
            f"환경 변수 {var}가 설정되지 않았습니다. .env에 {var}=... 값을 추가하세요."
        )
    return value


def tokenize(text: str) -> List[str]:
    """간단한 토큰화: 소문자화, 구두점 제거, 불용어/길이 필터."""
    tokens = []
    for raw in TOKEN_PATTERN.findall(text.lower()):
        if len(raw) < MIN_WORD_LEN:
            continue
        if raw in STOPWORDS:
            continue
        tokens.append(raw)
    return tokens


def count_keywords(contents: Iterable[str]) -> Counter:
    counter: Counter = Counter()
    for text in contents:
        counter.update(tokenize(text))
    # 빈도 필터
    for word in list(counter.keys()):
        if counter[word] < MIN_FREQ:
            del counter[word]
    return counter


def create_topics(driver, keywords: List[Tuple[str, int]]) -> None:
    def _tx(tx, items):
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


def link_blocks_to_topics(driver, blocks: List[Dict], topics: List[Tuple[str, int]]) -> None:
    topic_set = {w for w, _ in topics}
    links: List[Dict[str, str]] = []

    def flush(batch: List[Dict[str, str]]):
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
        for topic in matched:
            links.append({"block_id": block_id, "topic": topic})
        if len(links) >= REL_BATCH_SIZE:
            flush(links)
            links = []

    flush(links)
    logger.info("Block-Topic 관계 생성 완료")


def fetch_blocks(driver) -> List[Dict]:
    with driver.session() as session:
        result = session.run(
            """
            MATCH (b:Block)
            WHERE coalesce(b.content, '') <> '' AND size(b.content) > 10
            RETURN b.id AS id, b.content AS content
            """
        )
        return [dict(record) for record in result]


# --------------------
# 메인 흐름
# --------------------

def main() -> None:
    load_dotenv()

    try:
        config = {
            "uri": require_env("NEO4J_URI"),
            "user": require_env("NEO4J_USER"),
            "password": require_env("NEO4J_PASSWORD"),
        }
    except EnvironmentError as e:
        logger.error(str(e))
        sys.exit(1)

    driver = GraphDatabase.driver(config["uri"], auth=(config["user"], config["password"]))

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
