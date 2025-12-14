"""LangChain Callback Handler for Neo4j Logging module.

Implements a LangChain BaseCallbackHandler that records LLM call lifecycle events
(start, end, error) directly to a Neo4j graph database for audit and debugging.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import datetime
from typing import Any

from langchain.callbacks.base import BaseCallbackHandler
from neo4j import GraphDatabase

from src.config.utils import require_env
from src.infra.neo4j import SafeDriver, create_sync_driver


class Neo4jLoggingCallback(BaseCallbackHandler):
    """LangChain 콜백 이벤트를 Neo4j에 기록합니다."""

    def __init__(
        self,
        neo4j_uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        session_id: str | None = None,
    ):
        """Initialize the Neo4j logging callback.

        Args:
            neo4j_uri: Optional Neo4j database URI.
            user: Optional Neo4j username.
            password: Optional Neo4j password.
            session_id: Optional session identifier.
        """
        self.neo4j_uri = neo4j_uri or require_env("NEO4J_URI")
        self.neo4j_user = user or require_env("NEO4J_USER")
        self.neo4j_password = password or require_env("NEO4J_PASSWORD")
        self.session_id = session_id or datetime.now().isoformat()
        self.driver: SafeDriver = create_sync_driver(
            self.neo4j_uri,
            self.neo4j_user,
            self.neo4j_password,
            graph_db_factory=GraphDatabase.driver,
        )

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
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
        except Exception as exc:  # pragma: no cover - logging only
            logging.getLogger(__name__).warning("LLM start log failed: %s", exc)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
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
        except Exception as exc:  # pragma: no cover - logging only
            logging.getLogger(__name__).warning("LLM end log failed: %s", exc)

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
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
        except Exception as exc:  # pragma: no cover - logging only
            logging.getLogger(__name__).warning("LLM chain error log failed: %s", exc)

    def close(self) -> None:
        """Close the database connection."""
        if self.driver:
            self.driver.close()

    def __enter__(self) -> Neo4jLoggingCallback:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Exit context manager and close resources."""
        self.close()

    def __del__(self) -> None:
        """Destructor to ensure resources are cleaned up."""
        with suppress(Exception):
            self.close()


# 사용 예시:
# callback = Neo4jLoggingCallback()
# chain.invoke(input_dict, config={"callbacks": [callback]})
