from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain.callbacks.base import BaseCallbackHandler
from neo4j import GraphDatabase

from src.qa_rag_system import require_env


class Neo4jLoggingCallback(BaseCallbackHandler):
    """
    LangChain 콜백 이벤트를 Neo4j에 기록합니다.
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        session_id: Optional[str] = None,
    ):
        self.neo4j_uri = neo4j_uri or require_env("NEO4J_URI")
        self.neo4j_user = user or require_env("NEO4J_USER")
        self.neo4j_password = password or require_env("NEO4J_PASSWORD")
        self.session_id = session_id or datetime.now().isoformat()
        self.driver = GraphDatabase.driver(
            self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
        )

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs):
        """LLM 호출 시작."""
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    CREATE (call:LLMCall {
                        session_id: $sid,
                        prompts: $prompts,
                        started_at: datetime()
                    })
                    """,
                    sid=self.session_id,
                    prompts=str(prompts),
                )
        except Exception:
            pass

    def on_llm_end(self, response: Any, **kwargs):
        """LLM 호출 종료."""
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (call:LLMCall {session_id: $sid})
                    WHERE call.ended_at IS NULL
                    WITH call
                    ORDER BY call.started_at DESC
                    LIMIT 1
                    SET call.response = $response,
                        call.ended_at = datetime(),
                        call.duration = duration.between(call.started_at, datetime())
                    """,
                    sid=self.session_id,
                    response=str(response),
                )
        except Exception:
            pass

    def on_chain_error(self, error: Exception, **kwargs):
        """체인/LLM 에러 기록."""
        try:
            with self.driver.session() as session:
                session.run(
                    """
                    CREATE (err:Error {
                        session_id: $sid,
                        error: $error,
                        timestamp: datetime()
                    })
                    """,
                    sid=self.session_id,
                    error=str(error),
                )
        except Exception:
            pass

    def close(self):
        if self.driver:
            self.driver.close()


# 사용 예시:
# callback = Neo4jLoggingCallback()
# chain.invoke(input_dict, config={"callbacks": [callback]})
