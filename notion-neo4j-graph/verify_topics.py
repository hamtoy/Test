import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


def verify_topics():
    driver = GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )

    with driver.session() as session:
        # Topic 수 확인
        result = session.run("MATCH (t:Topic) RETURN count(t) as count")
        topic_count = result.single()["count"]

        # 연결된 관계 수 확인
        result = session.run("MATCH ()-[r:DISCUSSES]->() RETURN count(r) as count")
        rel_count = result.single()["count"]

        print(f"📊 의미 분석 결과 검증:")
        print(f"   - 생성된 토픽(Topic): {topic_count}개")
        print(f"   - 연결된 관계(DISCUSSES): {rel_count}개")

    driver.close()


if __name__ == "__main__":
    verify_topics()
