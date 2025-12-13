import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


def verify_import():
    """Neo4j 데이터 임포트 결과 검증."""
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]

    driver = GraphDatabase.driver(uri, auth=(user, password))

    with driver.session() as session:
        # 페이지 수 확인
        result = session.run("MATCH (p:Page) RETURN count(p) as count")
        page_count = result.single()["count"]

        # 블록 수 확인
        result = session.run("MATCH (b:Block) RETURN count(b) as count")
        block_count = result.single()["count"]

        # 관계 수 확인
        result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
        rel_count = result.single()["count"]

        print("📊 데이터 검증 결과:")
        print(f"   - 페이지(Page): {page_count}개")
        print(f"   - 블록(Block): {block_count}개")
        print(f"   - 관계(Relationship): {rel_count}개")

    driver.close()


if __name__ == "__main__":
    verify_import()
