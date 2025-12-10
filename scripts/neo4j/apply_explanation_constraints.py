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
        # 1. Create QueryType: explanation
        """
        MERGE (qt:QueryType {name: "explanation"})
        SET qt.display_name = "전체 설명형",
            qt.description = "이미지 전체 내용에 대한 종합적 설명"
        """,
        # 2. Constraint: comprehensive_explanation_query
        """
        MATCH (qt:QueryType {name: "explanation"})
        MERGE (c1:Constraint {
          name: "comprehensive_explanation_query",
          description: "질의는 이미지 전체 내용을 대상으로 한 종합적 설명을 요청. '이 이미지의 주요 내용에 대해 설명해 주십시오' 형식. 부분 설명 금지.",
          priority: 80,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c1)
        """,
        # 3. Constraint: structured_explanation_answer
        """
        MATCH (qt:QueryType {name: "explanation"})
        MERGE (c2:Constraint {
          name: "structured_explanation_answer",
          description: "답변은 논리적 구조로 작성: 도입(1-2문장) → 주요 내용(3-5개 포인트) → 결론(1-2문장). 불릿 포인트 사용 권장.",
          priority: 70,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c2)
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
