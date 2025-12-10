import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from neo4j import GraphDatabase

from src.config.settings import AppConfig


def main():
    print("Loading configuration...")
    try:
        config = AppConfig()
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return

    uri = config.neo4j_uri
    user = config.neo4j_user
    password = config.neo4j_password

    if not uri or not user or not password:
        print("Error: Neo4j configuration missing in .env or environment variables.")
        return

    print(f"Connecting to Neo4j at {uri}...")
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("Connection successful!")
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}")
        return

    queries = [
        # 1. Create QueryType: target_long
        """
        MERGE (qt:QueryType {name: "target_long"})
        SET qt.display_name = "타겟 장답형",
            qt.description = "핵심 요점 질의 (3-4문장 답변)"
        """,
        # 2. Constraint: key_point_query_format
        """
        MATCH (qt:QueryType {name: "target_long"})
        MERGE (c1:Constraint {
          name: "key_point_query_format",
          description: "질의는 핵심 요점을 묻는 형식 사용: '~의 주요 동향은 무엇입니까?', '~에서 중요한 변화는 무엇입니까?', '~의 핵심 내용은 무엇입니까?', '~의 주요 특징은 무엇입니까?'. 전체 설명이 아닌 핵심 요약 질의.",
          priority: 90,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c1)
        """,
        # 3. Constraint: answer_length_3_4_sentences
        """
        MATCH (qt:QueryType {name: "target_long"})
        MERGE (c2:Constraint {
          name: "answer_length_3_4_sentences",
          description: "답변은 3-4문장 이내로 작성. 최대 100단어 제한. 핵심 요점만 간결하게 제시하고 불필요한 반복 금지. 구조화된 간결한 답변.",
          priority: 90,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c2)
        """,
        # 4. Constraint: structured_key_points
        """
        MATCH (qt:QueryType {name: "target_long"})
        MERGE (c3:Constraint {
          name: "structured_key_points",
          description: "답변은 2-3개의 핵심 포인트로 구조화. 각 포인트는 명확하고 간결하게. 장황한 설명 금지. 필요시 불릿 포인트 사용 가능.",
          priority: 80,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c3)
        """,
    ]

    try:
        with driver.session() as session:
            for i, query in enumerate(queries):
                print(f"Executing query {i + 1}/{len(queries)}...")
                session.run(query)
        print("All constraints applied successfully!")
    except Exception as e:
        print(f"Error executing queries: {e}")
    finally:
        driver.close()


if __name__ == "__main__":
    main()
