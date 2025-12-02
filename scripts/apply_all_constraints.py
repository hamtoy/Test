import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from neo4j import GraphDatabase

from src.config.settings import AppConfig


def main():
    print("Loading configuration...", flush=True)
    try:
        config = AppConfig()
    except Exception as e:
        print(f"Error loading configuration: {e}", flush=True)
        return

    uri = config.neo4j_uri
    user = config.neo4j_user
    password = config.neo4j_password

    if not uri or not user or not password:
        print("Error: Neo4j configuration missing.", flush=True)
        return

    print(f"Connecting to Neo4j at {uri}...", flush=True)
    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        print("Connection successful!", flush=True)
    except Exception as e:
        print(f"Failed to connect to Neo4j: {e}", flush=True)
        return

    queries = [
        # ========================================
        # 1. target_short (타겟 단답형)
        # ========================================
        """
        MERGE (qt:QueryType {name: "target_short"})
        SET qt.display_name = "타겟 단답형",
            qt.description = "간단한 사실 확인 질의 (1-2문장 답변)"
        """,
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
        # ========================================
        # 2. target_long (타겟 장답형)
        # ========================================
        """
        MERGE (qt:QueryType {name: "target_long"})
        SET qt.display_name = "타겟 장답형",
            qt.description = "핵심 요점 질의 (3-4문장 답변)"
        """,
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
        # ========================================
        # 3. explanation (전체 설명형)
        # ========================================
        """
        MERGE (qt:QueryType {name: "explanation"})
        SET qt.display_name = "전체 설명형",
            qt.description = "이미지 전체 내용에 대한 종합적 설명"
        """,
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
        # ========================================
        # 4. reasoning (추론형)
        # ========================================
        """
        MERGE (qt:QueryType {name: "reasoning"})
        SET qt.display_name = "추론형",
            qt.description = "근거 기반 추론 및 전망"
        """,
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

    print(f"Total queries to execute: {len(queries)}", flush=True)

    try:
        with driver.session() as session:
            for i, query in enumerate(queries):
                print(f"Executing query {i + 1}/{len(queries)}...", flush=True)
                try:
                    session.run(query)
                except Exception as qe:
                    print(f"Failed to execute query {i + 1}: {qe}", flush=True)
                    # Continue to next query? Or stop? Let's stop to be safe.
                    raise qe
        print("All constraints applied successfully!", flush=True)
    except Exception as e:
        print(f"Error executing queries: {e}", flush=True)
    finally:
        if driver:
            driver.close()


if __name__ == "__main__":
    main()
