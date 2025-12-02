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
        print(
            f"URI: {uri}, User: {user}, Password: {'*' * len(password) if password else 'None'}"
        )
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
        # 1. Create QueryType
        """
        MERGE (qt:QueryType {name: "target_short"})
        SET qt.display_name = "타겟 단답형",
            qt.description = "간단한 사실 확인 질의 (1-2문장 답변)"
        """,
        # 2. Constraint: factual_query_format_only
        """
        MATCH (qt:QueryType {name: "target_short"})
        MERGE (c1:Constraint {
          name: "factual_query_format_only",
          description: "질의는 반드시 다음 형식만 허용됩니다: '~는 무엇입니까?', '~는 언제입니까?', '~는 어디입니까?', '~는 몇 개입니까?', '~는 얼마입니까?', '~의 주요 내용은 무엇입니까?' (핵심만 1-2문장으로 답할 수 있는 경우에만). 절대 금지: '~에 대해 설명해 주십시오', '~를 요약해 주십시오' 형식.",
          priority: 100,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c1)
        """,
        # 3. Constraint: no_explanation_style_query
        """
        MATCH (qt:QueryType {name: "target_short"})
        MERGE (c2:Constraint {
          name: "no_explanation_style_query",
          description: "설명형 질의 절대 금지: '~에 대해 설명해 주십시오', '~를 요약해 주십시오', '~를 분석해 주십시오' 형식 사용 불가. 오직 사실 확인 질의만 생성.",
          priority: 100,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c2)
        """,
        # 4. Constraint: answer_length_1_2_sentences
        """
        MATCH (qt:QueryType {name: "target_short"})
        MERGE (c3:Constraint {
          name: "answer_length_1_2_sentences",
          description: "답변은 반드시 1-2문장 이내로 작성. 최대 50단어 제한. 핵심만 추출하고 불필요한 서론, 결론, 예시, 부연 설명 절대 금지. 간결하고 직접적인 답변만 제공.",
          priority: 100,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c3)
        """,
        # 5. Constraint: direct_answer_no_introduction
        """
        MATCH (qt:QueryType {name: "target_short"})
        MERGE (c4:Constraint {
          name: "direct_answer_no_introduction",
          description: "답변은 질문에 대한 직접적인 답변으로 즉시 시작. '~에 대해 말씀드리면', '결론적으로' 등의 서론 표현 금지. 핵심 정보만 명확하게 제시.",
          priority: 90,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c4)
        """,
        # 5. Constraint: no_overlap_with_global_explanation
        """
        MATCH (qt:QueryType {name: "target_short"})
        MERGE (c5:Constraint {
          name: "no_overlap_with_global_explanation",
          description: "타겟 단답형 질의는 전체 설명형(global_explanation)에서 다루지 않은 세부 사실/수치를 묻는 질문이어야 합니다. 전체 설명에서 이미 언급된 핵심 내용과 중복되는 질의는 생성하지 마세요. 전체 흐름이 아닌 구체적 팩트(날짜, 수치, 특정 명칭 등)에 집중하세요.",
          priority: 95,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c5)
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
