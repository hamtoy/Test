"""Neo4j Template Rules Helper.

Neo4j에서 Jinja2 템플릿에 사용할 작업 가이드 규칙을 가져오는 헬퍼 모듈.
guide.csv와 qna.csv의 내용을 QueryType별로 필터링하여 반환.
"""

from functools import lru_cache
from typing import Any, Dict, List, Optional


@lru_cache(maxsize=128)
def get_rules_for_query_type(
    query_type: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> List[Dict[str, str]]:
    """Neo4j에서 특정 QueryType에 연결된 Guide Item 규칙 가져오기.

    Args:
        query_type: explanation, reasoning, target_short, target_long 등
        neo4j_uri: Neo4j 연결 URI
        neo4j_user: Neo4j 사용자명
        neo4j_password: Neo4j 비밀번호

    Returns:
        규칙 딕셔너리 리스트:
        [
            {
                'title': '1. 설명문 질의',
                'content': '질의 내용...',
                'category': '작업 안내',
                'subcategory': '질의'
            },
            ...
        ]
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (i:Item)-[:DESCRIBES_QUERY_TYPE]->(qt:QueryType {name: $query_type})
                RETURN i.categoryName as category,
                       i.subcategoryName as subcategory,
                       i.name as title,
                       i.content as content
                ORDER BY i.name
                """,
                query_type=query_type,
            )

            return [
                {
                    "title": record["title"],
                    "content": record["content"],
                    "category": record["category"],
                    "subcategory": record["subcategory"],
                }
                for record in result
            ]
    finally:
        driver.close()


@lru_cache(maxsize=128)
def get_common_mistakes(
    category: Optional[str],
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> List[Dict[str, str]]:
    """Neo4j에서 자주 틀리는 부분 (QATopic) 가져오기.

    Args:
        category (Optional[str]): 필터링할 카테고리. '질의', '답변', '작업 규칙' 등.
            None이면 모든 카테고리 반환 (최대 15개).
        neo4j_uri (str): Neo4j 데이터베이스 연결 URI.
        neo4j_user (str): Neo4j 사용자명.
        neo4j_password (str): Neo4j 비밀번호.

    Returns:
        List[Dict[str, str]]: 자주 틀리는 부분 리스트. 각 딕셔너리는 다음 키를 포함:
            - title (str): 실수 항목 제목 (예: '1. 문장이 부자연스러운 경우')
            - preview (str): 내용 미리보기 (최대 150자)
            - subcategory (str): 하위 카테고리 (예: '답변', '질의')

    Note:
        이 함수는 @lru_cache(maxsize=128)로 캐싱되므로 동일 인자로
        반복 호출 시 네트워크 요청 없이 즉시 반환됩니다.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        with driver.session() as session:
            if category:
                result = session.run(
                    """
                    MATCH (t:QATopic)
                    WHERE t.categoryName = '🙅 자주 틀리는 부분'
                      AND t.subcategoryName = $category
                    RETURN t.subcategoryName as subcategory,
                           t.name as title,
                           substring(t.content, 0, 150) as preview
                    ORDER BY t.name
                    LIMIT 10
                    """,
                    category=category,
                )
            else:
                result = session.run(
                    """
                    MATCH (t:QATopic)
                    WHERE t.categoryName = '🙅 자주 틀리는 부분'
                    RETURN t.subcategoryName as subcategory,
                           t.name as title,
                           substring(t.content, 0, 150) as preview
                    ORDER BY t.subcategoryName, t.name
                    LIMIT 15
                    """
                )

            return [
                {
                    "title": record["title"],
                    "preview": record["preview"],
                    "subcategory": record["subcategory"],
                }
                for record in result
            ]
    finally:
        driver.close()


@lru_cache(maxsize=64)
def get_best_practices(
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> List[str]:
    """Neo4j에서 Best Practice 관련 Item 가져오기.

    Args:
        neo4j_uri (str): Neo4j 데이터베이스 연결 URI.
        neo4j_user (str): Neo4j 사용자명.
        neo4j_password (str): Neo4j 비밀번호.

    Returns:
        List[str]: Best Practice 문자열 리스트 (최대 10개).
            각 항목은 "제목: 미리보기..." 형식.

    Note:
        이 함수는 @lru_cache(maxsize=64)로 캐싱됩니다.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (i:Item:BestPracticeRelated)
                RETURN i.name as title,
                       substring(i.content, 0, 200) as preview
                ORDER BY i.categoryName, i.subcategoryName, i.name
                LIMIT 10
                """
            )

            return [f"{record['title']}: {record['preview']}..." for record in result]
    finally:
        driver.close()


@lru_cache(maxsize=128)
def get_constraint_details(
    query_type: Optional[str],
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
) -> List[str]:
    """Neo4j에서 제약조건 관련 Item 가져오기.

    Args:
        query_type (Optional[str]): 특정 QueryType으로 필터링.
            None이면 모든 제약조건 반환.
        neo4j_uri (str): Neo4j 데이터베이스 연결 URI.
        neo4j_user (str): Neo4j 사용자명.
        neo4j_password (str): Neo4j 비밀번호.

    Returns:
        List[str]: 제약조건 문자열 리스트 (최대 15개).
            각 항목은 "제목: 미리보기(200자)..." 형식.

    Note:
        현재 구현은 query_type 파라미터를 사용하지 않고 모든 제약조건을 반환합니다.
        이 함수는 @lru_cache(maxsize=128)로 캐싱됩니다.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (i:Item:ConstraintRelated)
                RETURN i.name as title,
                       substring(i.content, 0, 200) as preview
                ORDER BY i.categoryName, i.subcategoryName, i.name
                LIMIT 15
                """
            )

            return [f"{record['title']}: {record['preview']}..." for record in result]
    finally:
        driver.close()


def get_all_template_context(
    query_type: str,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    include_mistakes: bool = True,
    include_best_practices: bool = False,
    include_constraints: bool = False,
    context_stage: str = "answer",  # "answer" or "query"
) -> Dict[str, Any]:
    """템플릿에 필요한 모든 컨텍스트를 한 번에 가져오기.

    Args:
        query_type: explanation, reasoning, etc.
        neo4j_uri: Neo4j 연결 URI
        neo4j_user: Neo4j 사용자명
        neo4j_password: Neo4j 비밀번호
        include_mistakes: 자주 틀리는 부분 포함 여부
        include_best_practices: Best Practice 포함 여부
        include_constraints: 제약조건 상세 포함 여부
        context_stage: 'answer' (답변 생성) 또는 'query' (질의 생성)

    Returns:
        템플릿 컨텍스트 딕셔너리
    """
    context: Dict[str, Any] = {
        "guide_rules": get_rules_for_query_type(
            query_type, neo4j_uri, neo4j_user, neo4j_password
        ),
    }

    if include_mistakes:
        # query_type에 맞는 카테고리 매핑
        if context_stage == "query":
            # 질의 생성 단계에서는 모두 '질의' 카테고리 실수 가져오기
            category = "질의"
        else:
            # 답변 생성 단계에서는 타입별 매핑
            mistake_category_map = {
                "explanation": "답변",
                "reasoning": "질의",  # 추론 질의는 질의 자체가 중요할 수 있음 (또는 답변) -> 일단 기존 유지
                "target_short": "질의",
                "target_long": "답변",
            }
            category = mistake_category_map.get(query_type, "답변")

        context["common_mistakes"] = get_common_mistakes(
            category, neo4j_uri, neo4j_user, neo4j_password
        )

    if include_best_practices:
        context["best_practices"] = get_best_practices(
            neo4j_uri, neo4j_user, neo4j_password
        )

    if include_constraints:
        context["constraint_details"] = get_constraint_details(
            query_type, neo4j_uri, neo4j_user, neo4j_password
        )

    return context


# 환경변수에서 Neo4j 설정 가져오기
def get_neo4j_config() -> Dict[str, str]:
    """환경변수에서 Neo4j 연결 정보 가져오기."""
    import os

    return {
        "neo4j_uri": os.getenv("NEO4J_URI", "neo4j+s://6a85a996.databases.neo4j.io"),
        "neo4j_user": os.getenv("NEO4J_USERNAME", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", ""),
    }
