from __future__ import annotations

import os
import sys
from typing import Dict, Any, List

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

load_dotenv()

REPO_ROOT = os.path.abspath(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from checks.validate_session import validate_turns  # noqa: E402


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class QAKnowledgeGraph:
    """
    RAG + 그래프 기반 QA 헬퍼.
    - Neo4j 그래프 쿼리
    - (선택) Rule 벡터 검색
    - 세션 구조 검증
    """

    def __init__(self):
        self.neo4j_uri = require_env("NEO4J_URI")
        self.neo4j_user = require_env("NEO4J_USER")
        self.neo4j_password = require_env("NEO4J_PASSWORD")
        self._graph = None
        self._vector_store = None
        self._init_graph()
        self._init_vector_store()

    def _init_graph(self):
        try:
            self._graph = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )
        except Neo4jError as e:
            raise RuntimeError(f"Neo4j 연결 실패: {e}")

    def _init_vector_store(self):
        """
        GEMINI_API_KEY로 임베딩을 생성합니다. 키가 없거나 인덱스가 없으면 건너뜀.
        """
        try:
            from langchain_neo4j import Neo4jVector
            import google.generativeai as genai

            class CustomGeminiEmbeddings:
                def __init__(
                    self, api_key: str, model: str = "models/text-embedding-004"
                ):
                    genai.configure(api_key=api_key)
                    self.model = model

                def embed_documents(self, texts: List[str]) -> List[List[float]]:
                    return [self.embed_query(text) for text in texts]

                def embed_query(self, text: str) -> List[float]:
                    result = genai.embed_content(
                        model=self.model, content=text, task_type="retrieval_query"
                    )
                    return result["embedding"]

            gemini_api_key = os.getenv("GEMINI_API_KEY")

            embedding_model = None
            if gemini_api_key:
                embedding_model = CustomGeminiEmbeddings(api_key=gemini_api_key)
            else:
                print(
                    "⚠️ GEMINI_API_KEY 미설정: 벡터 검색을 건너뜁니다."
                )
                return

            self._vector_store = Neo4jVector.from_existing_graph(
                embedding_model,
                url=self.neo4j_uri,
                username=self.neo4j_user,
                password=self.neo4j_password,
                index_name="rule_embeddings",
                node_label="Rule",
                text_node_properties=["text", "section"],
                embedding_node_property="embedding",
            )
        except Exception as e:
            print(f"⚠️ 벡터 스토어 초기화 실패: {e}")
            self._vector_store = None

    def find_relevant_rules(self, query: str, k: int = 5) -> List[str]:
        """벡터 검색 기반 규칙 찾기 (가능할 때만)."""
        if not self._vector_store:
            return []
        results = self._vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in results]

    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """
        QueryType과 연결된 제약 조건 조회.
        - Rule-[:APPLIES_TO]->QueryType, Rule-[:ENFORCES]->Constraint
        - Template-[:ENFORCES]->Constraint
        """
        cypher = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (r:Rule)-[:APPLIES_TO]->(qt)
        OPTIONAL MATCH (r)-[:ENFORCES]->(c1:Constraint)
        OPTIONAL MATCH (t:Template)-[:ENFORCES]->(c2:Constraint)
        WITH qt, collect(DISTINCT c1) + collect(DISTINCT c2) AS cons
        UNWIND cons AS c
        RETURN DISTINCT c.id AS id, c.description AS description, c.type AS type
        """
        with self._graph.session() as session:
            records = session.run(cypher, qt=query_type)
            return [dict(r) for r in records]

    def get_best_practices(self, query_type: str) -> List[Dict[str, str]]:
        cypher = """
        MATCH (qt:QueryType {name: $qt})<-[:APPLIES_TO]-(b:BestPractice)
        RETURN b.id AS id, b.text AS text
        """
        with self._graph.session() as session:
            return [dict(r) for r in session.run(cypher, qt=query_type)]

    def get_examples(self, limit: int = 5) -> List[Dict[str, str]]:
        """
        Example 노드 조회 (현재 Rule과 직접 연결되지 않았으므로 전체에서 샘플링).
        """
        cypher = """
        MATCH (e:Example)
        RETURN e.id AS id, e.text AS text, e.type AS type
        LIMIT $limit
        """
        with self._graph.session() as session:
            return [dict(r) for r in session.run(cypher, limit=limit)]

    def validate_session(self, session: dict) -> Dict[str, Any]:
        """
        checks/validate_session 로직을 활용해 세션 구조 검증.
        """
        from scripts.build_session import SessionContext

        turns = session.get("turns", [])
        if not turns:
            return {"ok": False, "issues": ["turns가 비어있습니다."]}

        ctx_kwargs = session.get("context", {})
        try:
            ctx = SessionContext(**ctx_kwargs)
            res = validate_turns([type("T", (), t) for t in turns], ctx)
            return res
        except Exception as exc:
            return {"ok": False, "issues": [f"컨텍스트 생성 실패: {exc}"]}

    def close(self):
        if self._graph:
            self._graph.close()


if __name__ == "__main__":
    kg = QAKnowledgeGraph()

    print("🔍 '설명문 작성' 관련 규칙 (벡터 검색):")
    for i, rule in enumerate(kg.find_relevant_rules("설명문을 어떻게 작성하나요?"), 1):
        print(f"  {i}. {rule[:120]}...")

    print("\n📋 'explanation' 유형 제약 조건:")
    for c in kg.get_constraints_for_query_type("explanation"):
        print(f"  - {c.get('id')}: {c.get('description')}")

    print("\n🧭 'explanation' 모범 사례:")
    for bp in kg.get_best_practices("explanation"):
        print(f"  - {bp['text']}")

    print("\n📑 예시 샘플:")
    for ex in kg.get_examples():
        print(f"  [{ex['type']}] {ex['text'][:80]}...")

    kg.close()
