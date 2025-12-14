"""Test Neo4J Connection module."""

import os

import pytest
from dotenv import load_dotenv

pytest.importorskip("neo4j")
from neo4j import GraphDatabase  # noqa: E402

load_dotenv()


@pytest.mark.skipif(
    not all(
        os.environ.get(var) for var in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")
    ),
    reason="Neo4j 환경 변수가 설정되지 않아 연결 테스트를 건너뜁니다.",
)
def test_neo4j_connection():
    """Neo4j Aura 연결 테스트."""
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        result = session.run("RETURN 'Connection successful!' AS message")
        record = result.single()
        assert record and record["message"]

        result = session.run(
            """
            CALL dbms.components() 
            YIELD name, versions, edition 
            RETURN name, versions[0] AS version, edition
            """
        )
        records = list(result)
        assert records

    driver.close()


if __name__ == "__main__":
    test_neo4j_connection()
