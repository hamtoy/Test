import os

import pytest
from dotenv import load_dotenv

pytest.importorskip("neo4j")
from neo4j import GraphDatabase  # noqa: E402

load_dotenv()


def test_neo4j_connection():
    """Neo4j Aura 연결 테스트"""

    uri = os.environ.get("NEO4J_URI")
    user = os.environ.get("NEO4J_USER")
    password = os.environ.get("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        pytest.skip("Neo4j 환경 변수가 설정되지 않아 연결 테스트를 건너뜁니다.")

    print("🔌 Neo4j Aura 연결 시도...")
    print(f"   URI: {uri}")
    print(f"   User: {user}")

    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 'Connection successful!' AS message")
            record = result.single()
            print(f"\n✅ {record['message']}")

            result = session.run(
                """
                CALL dbms.components() 
                YIELD name, versions, edition 
                RETURN name, versions[0] AS version, edition
                """
            )
            for record in result:
                print("\n📊 Neo4j 정보:")
                print(f"   Edition: {record['edition']}")
                print(f"   Version: {record['version']}")

        driver.close()
    except Exception as e:
        pytest.fail(f"Neo4j 연결 실패: {e}")


if __name__ == "__main__":
    test_neo4j_connection()
