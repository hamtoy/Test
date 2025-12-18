"""추론형(reasoning) 질의 유형에 대한 제약조건을 Neo4j에 적용."""

from __future__ import annotations

import os

from neo4j import GraphDatabase


def apply_reasoning_constraints() -> None:
    """추론형 제약조건을 Neo4j에 추가."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not (uri and user and password):
        print("Neo4j 환경변수가 설정되지 않았습니다.")
        return

    # mypy: ensure non-None after guard
    assert uri is not None and user is not None and password is not None

    driver = GraphDatabase.driver(uri, auth=(user, password))

    queries = [
        # QueryType 생성/업데이트
        """
        MERGE (qt:QueryType {name: "reasoning"})
        SET qt.display_name = "추론형",
            qt.description = "이미지 내 명시적 근거를 바탕으로 미래를 예측하는 질의"
        """,
        # 자연스러운 구조 제약 (라벨 금지)
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c:Constraint {
          name: "no_explicit_structure_labels",
          description: "추론형 답변에서 '근거', '추론 과정', '결론', '서론', '본론' 등 명시적 구조 라벨/소제목 사용을 절대 금지한다. 논리적 흐름은 자연스러운 연결어('이러한 배경에는', '이를 통해', '따라서' 등)로 전개한다.",
          priority: 100,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        """,
        # 자연스러운 연결어 사용 권장
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c:Constraint {
          name: "natural_transition_words",
          description: "문단 간 연결은 자연스러운 연결어를 사용한다. 권장 표현: '이러한 전망의 배경에는', '이러한 지표들은 ~을 보여줍니다', '특히', '또한', '이와 함께', '따라서', '결과적으로'. 금지 표현: '**근거**', '**추론 과정**', '**결론**', '첫째,', '둘째,'",
          priority: 95,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        """,
        # 두괄식 결론 제시
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c:Constraint {
          name: "deductive_conclusion_first",
          description: "추론형 답변은 두괄식으로 핵심 전망/결론을 첫 문단에 먼저 제시하고, 이어서 근거와 논리적 연결을 자연스럽게 서술한다. 마지막 문단에서 결론을 다시 요약한다.",
          priority: 90,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        """,
        # 요약문 헤더 금지
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c:Constraint {
          name: "no_summary_header",
          description: "'요약문', '요약:', '정리하면' 등의 헤더나 라벨 사용 금지. 답변 내용만 바로 서술한다.",
          priority: 100,
          category: "answer",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        """,
        # 추론 질의 어미 규칙 (query category)
        """
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (c:Constraint {
          name: "reasoning_query_verb_required",
          description: "추론 질의는 반드시 '추론해줘/전망해줘/예측해줘'처럼 미래를 예측하는 형태로 작성해야 한다. '설명해 주십시오', '설명해줘'와 같은 어미를 사용하면 설명문 질의와 혼동될 수 있으므로 금지한다. 예시: '한국 증시 전망에 대해 설명해줘(❌)' → '한국 증시 전망에 대해 추론해줘(⭕)'",
          priority: 100,
          category: "query",
          applies_to: "generation"
        })
        MERGE (qt)-[:HAS_CONSTRAINT]->(c)
        """,
    ]

    with driver.session() as session:
        for i, query in enumerate(queries, 1):
            try:
                session.run(query)
                print(f"✅ 쿼리 실행 완료 ({i}/{len(queries)})")
            except Exception as e:  # noqa: BLE001
                print(f"❌ 쿼리 실행 실패: {e}")

    driver.close()
    print("\n✅ 추론형 제약조건 적용 완료")


if __name__ == "__main__":
    apply_reasoning_constraints()
