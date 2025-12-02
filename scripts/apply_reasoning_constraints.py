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
        # 1. Create QueryType: reasoning
        """
        MERGE (qt:QueryType {name: "reasoning"})
        SET qt.display_name = "추론형",
            qt.description = "근거 기반 추론 및 전망"
        """,
        # 2. Constraint: inference_query_format
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c1:Constraint {
          name: "inference_query_format",
          description: "질의는 텍스트 내 근거를 바탕으로 한 추론/전망을 요청. '이 데이터를 바탕으로 향후 전망은 어떻습니까?', '이 추세가 지속된다면 어떤 결과가 예상됩니까?' 형식.",
          priority: 85,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c1)
        """,
        # 3. Constraint: reasoning_answer_structure
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c2:Constraint {
          name: "reasoning_answer_structure",
          description: "답변은 반드시 근거 제시 → 추론 과정 → 결론 순서로 작성. 근거 없는 추측 금지. '요약문' 같은 헤더 사용 금지. 각 근거는 텍스트 내용 인용.",
          priority: 90,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c2)
        """,
        # 4. Constraint: no_summary_header_in_reasoning
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c3:Constraint {
          name: "no_summary_header_in_reasoning",
          description: "추론형 답변에서 '요약문', '요약:', '결론 요약' 같은 헤더 절대 금지. 바로 근거와 추론으로 시작.",
          priority: 100,
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
