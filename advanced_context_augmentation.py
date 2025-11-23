from __future__ import annotations

from typing import Any, Dict, List, Optional

import os
from langchain_core.prompts import PromptTemplate
from langchain_community.graphs import Neo4jGraph
from langchain_community.vectorstores import Neo4jVector
from qa_rag_system import CustomGeminiEmbeddings


class AdvancedContextAugmentation:
    """
    유사 사례/규칙/예시를 찾아 프롬프트에 주입하는 보조 유틸.
    - GEMINI_API_KEY가 없으면 벡터 검색을 건너뛰고 그래프 기반 정보만 사용.
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
                node_label="Block",  # Rule, Example도 포함한다고 가정
                text_node_properties=["content", "text"],
                embedding_node_property="embedding",
            )

    def augment_prompt_with_similar_cases(
        self, user_query: str, query_type: str
    ) -> Dict[str, Any]:
        """
        유사한 블록/규칙/예시를 찾아 컨텍스트를 구성.
        벡터 인덱스가 없으면 그래프 검색만 수행.
        """

        similar_blocks: List[Any] = []
        if self.vector_index:
            similar_blocks = self.vector_index.similarity_search(user_query, k=5)

        block_ids = [
            b.metadata.get("id")
            for b in similar_blocks
            if isinstance(b.metadata, dict) and b.metadata.get("id") is not None
        ]

        enriched_rules: List[Dict[str, Any]] = []
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

        return {
            "similar_cases": [b.page_content for b in similar_blocks],
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
