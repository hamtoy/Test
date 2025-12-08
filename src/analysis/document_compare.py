"""Neo4j 그래프에 저장된 Page/Block을 비교/요약하는 스크립트.

개선 사항:
- 환경 변수 검증 후 친절한 오류 메시지
- 드라이버/세션을 컨텍스트로 관리해 자원 정리 보장
- 블록이 없는 페이지에서 null 타입이 섞이는 문제 방지
- 공통 콘텐츠 탐색 시 카티전 곱을 피하고 content별 그룹화로 성능/정확도 개선
"""

from __future__ import annotations

import sys
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from src.config.utils import require_env


def compare_structure(driver: Any) -> list[dict[str, Any]]:
    """페이지별 블록 구조 요약."""
    query = """
    MATCH (p:Page)
    OPTIONAL MATCH (p)-[:CONTAINS*]->(b:Block)
    WITH p, collect(DISTINCT b.type) AS block_types, count(DISTINCT b) AS total_blocks
    RETURN p.title AS title,
           total_blocks AS total_blocks,
           [t IN block_types WHERE t IS NOT NULL] AS types
    ORDER BY total_blocks DESC
    """
    with driver.session() as session:
        result = session.run(query)
        return [
            {
                "title": record["title"],
                "total": record["total_blocks"],
                "types": record["types"],
            }
            for record in result
        ]


def find_common_content(driver: Any, limit: int = 10) -> list[tuple[str, list[str]]]:
    """여러 페이지에서 동일하게 등장하는 블록 콘텐츠 찾기.

    content별로 그룹화하여 카티전 곱을 피함.
    """
    query = """
    MATCH (p:Page)-[:CONTAINS*]->(b:Block)
    WHERE b.content IS NOT NULL AND size(b.content) > 20
    WITH b.content AS content, collect(DISTINCT p.title) AS pages
    WHERE size(pages) > 1
    RETURN content, pages
    ORDER BY size(pages) DESC, size(content) DESC
    LIMIT $limit
    """
    with driver.session() as session:
        result = session.run(query, limit=limit)
        return [(record["content"], record["pages"]) for record in result]


def main() -> None:
    """Entry point for document comparison script."""
    load_dotenv()
    try:
        uri = require_env("NEO4J_URI")
        user = require_env("NEO4J_USER")
        password = require_env("NEO4J_PASSWORD")
    except OSError as e:
        print(str(e))
        sys.exit(1)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        structures = compare_structure(driver)
        print("📊 문서 구조 비교:\n")
        for s in structures:
            types_preview = ", ".join(s["types"][:10]) if s["types"] else "-"
            print(f"📄 {s['title']}")
            print(f"   총 블록: {s['total']}")
            print(f"   블록 타입 종류: {len(s['types'])}")
            print(f"   타입: {types_preview}\n")

        commons = find_common_content(driver, limit=10)
        print("🔗 공통으로 등장하는 내용:\n")
        for content, pages in commons:
            snippet = content[:80] + ("..." if len(content) > 80 else "")
            print(f"   '{snippet}'")
            print(f"   → {' ↔ '.join(pages)}\n")

    except Neo4jError as e:
        print(f"Neo4j 오류: {e}")
        sys.exit(1)
    finally:
        driver.close()


if __name__ == "__main__":
    main()
