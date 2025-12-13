import os

import pytest
from dotenv import load_dotenv

pytest.importorskip("notion_client")
pytest.importorskip("neo4j")

from neo4j import GraphDatabase  # noqa: E402
from notion_client import Client  # noqa: E402

load_dotenv()


def test_all():
    """Notion과 Neo4j 연결 모두 테스트."""
    token = os.environ.get("NOTION_TOKEN")
    page_id = os.environ.get("PAGE_ID_1")
    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")

    if not all([token, page_id, uri, user, password]):
        pytest.skip("Notion/Neo4j 환경 변수가 설정되지 않아 연결 테스트를 건너뜁니다.")

    print("=" * 50)
    print("🧪 통합 연결 테스트")
    print("=" * 50)

    # 1. Notion 테스트
    print("\n[1/2] Notion API 테스트...")
    notion = Client(auth=token)
    res = notion.pages.retrieve(page_id)
    assert res

    # 2. Neo4j 테스트
    print("\n[2/2] Neo4j Aura 테스트...")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 1")
        assert result.single()
    driver.close()
    print("✅ 통합 연결 성공")


if __name__ == "__main__":
    test_all()
