from __future__ import annotations

import logging
from typing import Dict, List, Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase
from src.qa.rag_system import CustomGeminiEmbeddings, require_env
from src.neo4j_utils import create_sync_driver, SafeDriver
from src.gemini_model_client import GeminiModelClient

load_dotenv()


class MemoryAugmentedQASystem:
    """
    세션 간 맥락을 기억하면서 벡터 검색+Gemini로 응답 생성.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        session_id: str = "qa_session_001",
    ):
        self.neo4j_uri = neo4j_uri or require_env("NEO4J_URI")
        self.neo4j_user = user or require_env("NEO4J_USER")
        self.neo4j_password = password or require_env("NEO4J_PASSWORD")
        self.session_id = session_id

        # Neo4j 드라이버
        self._driver: SafeDriver = create_sync_driver(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
            graph_db_factory=GraphDatabase.driver,
        )

        # 임베딩/벡터 스토어(Gemini 임베딩)
        from langchain_neo4j import Neo4jVector

        self.vectorstore = Neo4jVector.from_existing_graph(
            CustomGeminiEmbeddings(api_key=require_env("GEMINI_API_KEY")),
            url=self.neo4j_uri,
            username=self.neo4j_user,
            password=self.neo4j_password,
            index_name="qa_knowledge_base",
            node_label="Block",
            text_node_properties=["content", "text"],
            embedding_node_property="embedding",
        )

        self.llm = GeminiModelClient()
        self.history: List[Dict[str, str]] = []

    def ask_with_memory(self, question: str) -> str:
        """
        이전 대화와 벡터 검색 결과를 포함해 Gemini로 답변합니다.
        """

        # 벡터 검색 컨텍스트
        context_docs = self.vectorstore.similarity_search(question, k=5)
        context_text = "\n".join([d.page_content for d in context_docs])

        # 간단한 히스토리 직렬화
        history_text = "\n".join(
            [f"Q: {h['q']}\nA: {h['a']}" for h in self.history[-5:]]
        )

        prompt = f"""다음은 이전 대화와 검색된 문맥입니다.

[히스토리]
{history_text or "(없음)"}

[검색 컨텍스트]
{context_text}

[질문]
{question}

위 정보를 참고하여 한국어로 간결하고 근거 기반으로 답변하세요. 표/그래프는 참조하지 마세요."""

        answer = self.llm.generate(prompt, role="chat")

        # 기록 저장
        self.history.append({"q": question, "a": answer})
        self._log_interaction(question, answer)

        return answer

    def _log_interaction(self, question: str, answer: str) -> None:
        """상호작용을 그래프에 기록."""

        try:
            with self._driver.session() as session:
                session.run(
                    """
                    CREATE (i:Interaction {
                        session_id: $sid,
                        question: $question,
                        answer: $answer,
                        timestamp: datetime()
                    })
                    WITH i
                    MATCH (r:Rule)
                    WHERE $answer CONTAINS r.text
                    MERGE (i)-[:REFERENCED]->(r)
                    """,
                    sid=self.session_id,
                    question=question,
                    answer=answer,
                )
        except Exception as exc:  # pragma: no cover - best-effort logging
            logging.getLogger(__name__).warning("Interaction log failed: %s", exc)

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def __enter__(self) -> "MemoryAugmentedQASystem":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        self.close()
