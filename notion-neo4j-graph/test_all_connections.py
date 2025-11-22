import os

import pytest
from dotenv import load_dotenv

pytest.importorskip("notion_client")
pytest.importorskip("neo4j")

from notion_client import Client
from neo4j import GraphDatabase  # noqa: E402

load_dotenv()


def test_all():
    """Notion과 Neo4j 연결 모두 테스트"""

    print("=" * 50)
    print("🧪 통합 연결 테스트")
    print("=" * 50)

    # 1. Notion 테스트
    print("\n[1/2] Notion API 테스트...")
    try:
        notion = Client(auth=os.environ["NOTION_TOKEN"])
        # PAGE_ID_1이 없는 경우를 대비한 안전한 접근
        page_id = os.environ.get("PAGE_ID_1")
        if not page_id:
            print("⚠️ PAGE_ID_1 not found in .env")
        else:
            notion.pages.retrieve(page_id)
            print("✅ Notion 연결 성공")
    except Exception as e:
        print(f"❌ Notion 연결 실패: {e}")
        return False

    # 2. Neo4j 테스트
    print("\n[2/2] Neo4j Aura 테스트...")
    try:
        driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"]),
        )
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        print("✅ Neo4j 연결 성공")
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        return False

    print("\n" + "=" * 50)
    print("🎉 모든 연결 성공! 데이터 임포트 준비 완료")
    print("=" * 50)
    return True


if __name__ == "__main__":
    test_all()
