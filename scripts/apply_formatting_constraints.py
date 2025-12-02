"""서식 관련 제약조건을 Neo4j에 적용하는 스크립트."""

from __future__ import annotations

import os

from neo4j import GraphDatabase


def apply_formatting_constraints() -> None:
    """서식 관련 제약조건을 Neo4j에 추가."""
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")

    if not all([uri, user, password]):
        print("Neo4j 환경변수가 설정되지 않았습니다.")
        return

    driver = GraphDatabase.driver(uri, auth=(user, password))

    queries = [
        # 1. FormattingRule 노드 타입 생성 및 볼드체 규칙
        """
        MERGE (fr:FormattingRule {name: "bold_usage_restriction"})
        SET fr.description = "볼드체(**)는 오직 소제목과 목록형 답변의 핵심 키워드에만 구조적 역할로 사용한다. 줄글 본문 내 특정 단어 강조 목적으로는 절대 사용하지 않는다.",
            fr.priority = 100,
            fr.category = "formatting",
            fr.applies_to = "all",
            fr.examples_good = "**매출 현황** (소제목), - **매출**: 증가 (목록)",
            fr.examples_bad = "**달러화**는 상승했습니다. (본문 내 강조 금지)"
        """,
        # 2. 모든 QueryType에 연결
        """
        MATCH (fr:FormattingRule {name: "bold_usage_restriction"})
        MATCH (qt:QueryType)
        MERGE (qt)-[:HAS_FORMATTING_RULE]->(fr)
        """,
        # 추론형 답변 구조 규칙
        """
        MERGE (fr:FormattingRule {name: "natural_reasoning_structure"})
        SET fr.description = "추론형 답변에서 '근거', '추론 과정', '결론'과 같은 명시적 라벨/소제목 사용을 금지한다. 서론-본론-결론의 3단 구조는 유지하되, '이러한 전망의 배경에는', '이러한 지표들은', '따라서' 등 자연스러운 연결어로 논리적 흐름을 전개한다.",
            fr.priority = 95,
            fr.category = "answer",
            fr.applies_to = "reasoning",
            fr.examples_good = "전망의 배경에는... 이러한 지표들은... 따라서...",
            fr.examples_bad = "**근거**\\n- 내용...\\n**추론 과정**\\n내용...\\n**결론**\\n내용..."
        """,
        """
        MATCH (fr:FormattingRule {name: "natural_reasoning_structure"})
        MATCH (qt:QueryType {name: "reasoning"})
        MERGE (qt)-[:HAS_FORMATTING_RULE]->(fr)
        """,
        # 3. 복합 질문 금지 규칙
        """
        MERGE (fr:FormattingRule {name: "atomic_query_principle"})
        SET fr.description = "하나의 질의는 반드시 하나의 명확한 정보 또는 하나의 논리적 과업만을 요구해야 한다. 복합적인 요구사항(병렬 나열, 와/과로 연결)은 절대 금지한다.",
            fr.priority = 95,
            fr.category = "query",
            fr.applies_to = "all",
            fr.examples_bad = "S&P 500의 상승률과 한국 증시의 전망은 무엇입니까?"
        """,
        # 4. 모든 QueryType에 연결
        """
        MATCH (fr:FormattingRule {name: "atomic_query_principle"})
        MATCH (qt:QueryType)
        MERGE (qt)-[:HAS_FORMATTING_RULE]->(fr)
        """,
        # 5. 시의성 표현 규칙
        """
        MERGE (fr:FormattingRule {name: "time_reference_protocol"})
        SET fr.description = "'현재', '최근', '올해', '전일', '이번' 등 상대적 시간 표현은 단독 사용 금지. 반드시 기준점을 명시한다. (예: '(보고서 작성 시점 기준)', '(이미지 기준)')",
            fr.priority = 90,
            fr.category = "formatting",
            fr.applies_to = "all"
        """,
        # 6. 모든 QueryType에 연결
        """
        MATCH (fr:FormattingRule {name: "time_reference_protocol"})
        MATCH (qt:QueryType)
        MERGE (qt)-[:HAS_FORMATTING_RULE]->(fr)
        """,
    ]

    with driver.session() as session:
        for query in queries:
            try:
                session.run(query)
                print("✅ 쿼리 실행 완료")
            except Exception as e:  # noqa: BLE001
                print(f"❌ 쿼리 실행 실패: {e}")

    driver.close()
    print("\n✅ 서식 제약조건 적용 완료")


if __name__ == "__main__":
    apply_formatting_constraints()
