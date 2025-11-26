from __future__ import annotations

from typing import Any, Dict, List, Optional

import os
from langchain_core.prompts import PromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from src.qa_rag_system import CustomGeminiEmbeddings


class AdvancedContextAugmentation:
    """
    유사 사례/규칙/예시를 찾아 프롬프트에 주입하는 보조 유틸.
    - GEMINI_API_KEY가 없으면 벡터 검색을 건너뛰고 그래프 기반 대체 검색을 사용.
    """

    def __init__(
        self,
        neo4j_uri: str,
        user: str,
        password: str,
        gemini_key: Optional[str] = None,
    ):
        self.graph = Neo4jGraph(url=neo4j_uri, username=user, password=password)

        self.vector_index: Optional[Neo4jVector] = None
        self.llm = None

        # GEMINI_API_KEY를 우선 사용
        key = gemini_key or os.getenv("GEMINI_API_KEY")
        if key:
            self.vector_index = Neo4jVector.from_existing_graph(
                CustomGeminiEmbeddings(api_key=key),
                url=neo4j_uri,
                username=user,
                password=password,
                index_name="combined_embeddings",
                node_label="Block",  # Block 노드만 벡터 인덱싱.
                # Rule/Example 노드는 Block-[:RELATED_TO]->Rule 관계를 통해 간접 조회하여
                # 벡터 인덱스 크기를 줄이고 검색 효율성 확보.
                text_node_properties=["content", "text"],
                embedding_node_property="embedding",
            )

    def augment_prompt_with_similar_cases(
        self, user_query: str, query_type: str
    ) -> Dict[str, Any]:
        """유사 사례/규칙을 찾아 프롬프트 컨텍스트를 증강합니다.

        벡터 인덱스가 있으면 임베딩 기반으로 Block을 검색하고, 없으면 QueryType
        관계를 활용한 그래프 기반 대체 검색을 수행해 관련 규칙/예시를 수집합니다.

        Args:
            user_query: 사용자 입력 문장
            query_type: 질의 유형 (예: "explanation", "summary")

        Returns:
            다음 키를 포함하는 딕셔너리:
            - similar_cases (List[str]): 유사 Block 콘텐츠 텍스트 리스트
            - relevant_rules (List[Dict[str, Any]]): 규칙 정보, 각 Dict는 다음 포함:
                - rule (str): 규칙 텍스트
                - priority (int): 우선순위 (높을수록 중요)
                - examples (List[str]): 관련 예시 리스트 (최대 2개)
            - query_type (str): 입력 질의 유형

        Example:
            >>> aug = AdvancedContextAugmentation(uri, user, pwd, key)
            >>> result = aug.augment_prompt_with_similar_cases("설명문 작성", "explanation")
            >>> len(result["similar_cases"])
            5
            >>> result["relevant_rules"][0]["priority"]
            1
        """

        similar_blocks: List[Any] = []
        enriched_rules: List[Dict[str, Any]] = []

        if self.vector_index:
            similar_blocks = self.vector_index.similarity_search(user_query, k=5)

            block_ids = [
                b.metadata.get("id")
                for b in similar_blocks
                if isinstance(b.metadata, dict) and b.metadata.get("id") is not None
            ]

            if block_ids:
                with self.graph._driver.session() as session:
                    result = session.run(
                        """
                        MATCH (b:Block)
                        WHERE id(b) IN $block_ids
                        MATCH (b)-[:RELATED_TO]->(r:Rule)
                        OPTIONAL MATCH (r)<-[:DEMONSTRATES]-(e:Example)
                        WHERE e.type = 'positive'
                        RETURN DISTINCT
                            r.text AS rule,
                            r.priority AS priority,
                            collect(DISTINCT e.text)[0..2] AS examples
                        ORDER BY r.priority DESC
                        LIMIT 5
                        """,
                        block_ids=block_ids,
                    )
                    enriched_rules = result.data()
        else:
            # 백업: QueryType 기반 그래프 조회로 규칙/예시/블록을 가져옵니다.
            try:
                with self.graph._driver.session() as session:
                    record = session.run(
                        """
                        MATCH (qt:QueryType {name: $qt})
                        OPTIONAL MATCH (qt)<-[:RELATED_TO]-(b:Block)
                        WITH qt, collect(DISTINCT b)[0..5] AS blocks
                        OPTIONAL MATCH (qt)<-[:APPLIES_TO]-(r:Rule)
                        OPTIONAL MATCH (r)<-[:DEMONSTRATES]-(e:Example)
                        WHERE r IS NOT NULL AND (e IS NULL OR e.type = 'positive')
                        WITH blocks, r, [x IN collect(DISTINCT e.text) WHERE x IS NOT NULL][0..2] AS ex
                        RETURN blocks,
                               collect(DISTINCT {rule: r.text, priority: r.priority, examples: ex})[0..5] AS rules
                        """,
                        qt=query_type,
                    ).single()

                    if record:
                        similar_blocks = record.get("blocks") or []
                        enriched_rules = record.get("rules") or []
            except Exception as exc:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).warning(
                    "Fallback graph search failed: %s", exc
                )

        return {
            "similar_cases": [
                str(
                    getattr(b, "page_content", "")
                    or (b.get("content") if hasattr(b, "get") else "")
                    or (b.get("text") if hasattr(b, "get") else "")
                )
                for b in similar_blocks
                if getattr(b, "page_content", None)
                or (hasattr(b, "get") and (b.get("content") or b.get("text")))
            ],
            "relevant_rules": enriched_rules,
            "query_type": query_type,
        }

    def generate_with_augmentation(
        self, user_query: str, query_type: str, base_context: Dict[str, Any]
    ) -> str:
        """
        증강된 컨텍스트로 최종 프롬프트 생성 (LLM 호출 없이 포맷만 반환).
        """

        aug_ctx = self.augment_prompt_with_similar_cases(user_query, query_type)

        template = """
You are generating a {query_type} for text-image QA.

## Similar Successful Cases:
{similar_cases}

## Critical Rules (Auto-retrieved):
{rules}

## Positive Examples:
{examples}

## User Request:
{user_query}

## Base Context:
{base_context}

Generate output that follows ALL rules and learns from successful cases.
"""

        prompt = PromptTemplate(
            input_variables=[
                "query_type",
                "similar_cases",
                "rules",
                "examples",
                "user_query",
                "base_context",
            ],
            template=template,
        )

        formatted = prompt.format(
            query_type=query_type,
            similar_cases="\n".join(
                [f"- {c[:100]}..." for c in aug_ctx["similar_cases"]]
            )
            or "(none)",
            rules="\n".join(
                [
                    f"[P{r.get('priority', '?')}] {r.get('rule', '')}"
                    for r in aug_ctx["relevant_rules"]
                ]
            )
            or "(none)",
            examples="\n".join(
                [ex for r in aug_ctx["relevant_rules"] for ex in r.get("examples", [])]
            )
            or "(none)",
            user_query=user_query,
            base_context=str(base_context),
        )

        return formatted
