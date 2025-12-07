# mypy: disable-error-code=attr-defined
"""QA Knowledge Graph - RAG System with Neo4j Integration (Refactored).

This module provides the QAKnowledgeGraph class - a simplified facade that delegates
to specialized modules in src/qa/graph/ for actual functionality.

## Architecture (PROMPT-003 Refactoring)

**Delegation Pattern**:
- Connection Management → graph/connection.py (initialize_connection, close_connections)
- Vector Search → graph/vector_search.py (VectorSearchEngine)
- Rule Operations → graph/rule_upsert.py (RuleUpsertManager)
- Query Execution → graph/query_executor.py (QueryExecutor)
- Session Management → graph/connection.py (create_graph_session)
- Validators → graph/validators.py

**Main Class**:
- QAKnowledgeGraph: Facade coordinating graph operations

**Refactoring Goals** (712 lines → ~400 lines):
- ✅ Extract connection management
- ✅ Extract session management
- ✅ Extract connection cleanup
- ✅ Use QueryExecutor for consistent query execution
- ✅ Maintain backward compatibility
- ✅ All RAG tests passing

For architecture details: docs/ARCHITECTURE.md
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager, suppress
from typing import Any, Dict, Generator, List, Optional

import google.generativeai as genai  # noqa: F401
from dotenv import load_dotenv
from neo4j import GraphDatabase  # noqa: F401 - Imported for backward compatibility with test mocking

from src.caching.analytics import CacheMetrics
from src.config import AppConfig
from src.core.factory import get_graph_provider
from src.core.interfaces import GraphProvider
from src.infra.metrics import measure_latency
from src.qa.graph.connection import (
    close_connections,
    create_graph_session,
    initialize_connection,
)
from src.qa.graph.queries import CypherQueries
from src.qa.graph.query_executor import QueryExecutor
from src.qa.graph.rule_manager import RuleManager
from src.qa.graph.rule_upsert import RuleUpsertManager
from src.qa.graph.utils import (
    CustomGeminiEmbeddings,
    ensure_formatting_rule_schema,
    format_rules,
    init_vector_store,
    len_if_sized,
    record_vector_metrics,
)
from src.qa.graph.validators import (  # noqa: F401
    validate_session_structure,
    validate_turns,
)

logger = logging.getLogger(__name__)
__all__ = ["QAKnowledgeGraph", "CustomGeminiEmbeddings"]


load_dotenv()


class QAKnowledgeGraph:
    """RAG + 그래프 기반 QA 헬퍼.

    - Neo4j 그래프 쿼리
    - (선택) Rule 벡터 검색
    - 세션 구조 검증

    Simplified facade that delegates to specialized modules:
    - Connection management → graph/connection.py
    - Vector search → graph/vector_search.py
    - Rule operations → graph/rule_upsert.py
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        graph_provider: Optional[GraphProvider] = None,
        config: Optional[AppConfig] = None,
    ) -> None:
        """Initialize the QA Knowledge Graph.

        Args:
            neo4j_uri: Optional Neo4j database URI.
            neo4j_user: Optional Neo4j username.
            neo4j_password: Optional Neo4j password.
            graph_provider: Optional pre-configured graph provider.
            config: Optional application configuration.
        """
        cfg = config or AppConfig()
        provider = (
            graph_provider if graph_provider is not None else get_graph_provider(cfg)
        )
        self._graph_provider: Optional[GraphProvider] = provider
        self._cache_metrics = CacheMetrics(namespace="qa_kg")
        self._closed = False  # Track whether close() has been called

        # Store credentials for later use
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")

        # Initialize connection using helper function
        self._graph, self._graph_finalizer = initialize_connection(
            self.neo4j_uri, self.neo4j_user, self.neo4j_password, provider
        )

        # Initialize query executor for consistent query execution
        self._query_executor = QueryExecutor(
            graph_driver=self._graph,
            graph_provider=self._graph_provider,
        )

        # Initialize vector store (lazy, optional)
        self._vector_store: Any = None
        self._init_vector_store()

        # Initialize RuleUpsertManager for delegation
        self._rule_upsert_manager = RuleUpsertManager(
            graph=self._graph,
            graph_provider=self._graph_provider,
        )

        # Initialize RuleManager for CRUD operations
        self._rule_manager = RuleManager(self.graph_session)

        # Ensure required formatting rule schema is present
        ensure_formatting_rule_schema(
            driver=self._graph, provider=self._graph_provider, logger=logger
        )

    @property
    def cache_metrics(self) -> CacheMetrics:
        """Lazy-initialize cache metrics for cases where __init__ is bypassed in tests."""
        if not hasattr(self, "_cache_metrics") or self._cache_metrics is None:
            self._cache_metrics = CacheMetrics(namespace="qa_kg")
        return self._cache_metrics

    @property
    def query_executor(self) -> QueryExecutor:
        """Lazy-initialize query executor for cases where __init__ is bypassed in tests."""
        if not hasattr(self, "_query_executor") or self._query_executor is None:
            _executor = QueryExecutor(
                graph_driver=getattr(self, "_graph", None),
                graph_provider=getattr(self, "_graph_provider", None),
            )
            object.__setattr__(self, "_query_executor", _executor)
        return self._query_executor

    def _init_vector_store(self) -> None:
        """GEMINI_API_KEY로 임베딩을 생성합니다. 실패 시 graceful fallback."""
        if not os.getenv("GEMINI_API_KEY"):
            # 환경변수 없으면 현재 값을 유지하고 조용히 반환
            logger.debug(
                "GEMINI_API_KEY not set; skipping vector store initialization."
            )
            return

        try:
            new_store = init_vector_store(
                neo4j_uri=self.neo4j_uri,
                neo4j_user=self.neo4j_user,
                neo4j_password=self.neo4j_password,
                logger=logger,
            )
            self._vector_store = new_store
            logger.info("Vector store initialized successfully")
        except (ValueError, RuntimeError, ImportError) as e:
            logger.warning(
                "Failed to initialize vector store: %s. Continuing without RAG.", e
            )
            self._vector_store = None  # 명시적으로 None 설정
        except Exception as e:
            logger.error(
                "Unexpected error initializing vector store: %s", e, exc_info=True
            )
            self._vector_store = None

    @measure_latency(
        "vector_search",
        get_extra=lambda args,
        kwargs,
        result,
        success,
        elapsed_ms: record_vector_metrics(
            args[0].cache_metrics,
            query=kwargs.get("query", args[1]),
            k=kwargs.get("k", args[2] if len(args) > 2 else 5),
            result_count=len_if_sized(result),
            success=success,
            duration_ms=elapsed_ms,
        ),
    )
    def find_relevant_rules(self, query: str, k: int = 5) -> List[str]:
        """Return vector-search-based rules when available."""
        if not self._vector_store:
            self.cache_metrics.record_skip("vector_store_unavailable")
            logger.warning("Vector store unavailable; skipping vector search")
            return []

        results = self._vector_store.similarity_search(query, k=k)
        return [doc.page_content for doc in results]

    @measure_latency(
        "get_constraints",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1]),
            "result_count": len_if_sized(result),
        },
    )
    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """QueryType과 연결된 제약 조건 조회.

        - QueryType-[:HAS_CONSTRAINT]->Constraint 관계 사용
        """
        return self.query_executor.execute_with_fallback(
            CypherQueries.GET_CONSTRAINTS_FOR_QUERY_TYPE,
            params={"qt": query_type},
            default=[],
        )

    @measure_latency(
        "get_rules_for_query_type",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1]),
            "result_count": len_if_sized(result),
        },
    )
    def get_rules_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """Rule 노드 조회 (APPLIES_TO 관계 또는 applies_to 속성 기반)."""
        return self.query_executor.execute_with_fallback(
            CypherQueries.GET_RULES_FOR_QUERY_TYPE,
            params={"qt": query_type},
            default=[],
        )

    @measure_latency(
        "get_best_practices",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1]),
            "result_count": len_if_sized(result),
        },
    )
    def get_best_practices(self, query_type: str) -> List[Dict[str, str]]:
        """Get best practices for a given query type.

        Args:
            query_type: The type of query to get best practices for.

        Returns:
            List of best practice dictionaries with id and text.
        """
        return self.query_executor.execute_with_fallback(
            CypherQueries.GET_BEST_PRACTICES,
            params={"qt": query_type},
            default=[],
        )

    @measure_latency(
        "get_examples",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "limit": kwargs.get("limit", args[1] if len(args) > 1 else 5),
            "result_count": len_if_sized(result),
        },
    )
    def get_examples(self, limit: int = 5) -> List[Dict[str, str]]:
        """Example 노드 조회 (현재 Rule과 직접 연결되지 않았으므로 전체에서 샘플링)."""
        return self.query_executor.execute_with_fallback(
            CypherQueries.GET_EXAMPLES,
            params={"limit": limit},
            default=[],
        )

    @measure_latency(
        "validate_session",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "turns_count": len(kwargs.get("session", args[1]).get("turns", [])),
            "success": success,
        },
    )
    def validate_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """checks/validate_session 로직을 활용해 세션 구조 검증."""
        return validate_session_structure(session)

    @measure_latency(
        "upsert_auto_generated_rules",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "patterns_count": len(args[1]) if len(args) > 1 else 0,
            "batch_id": kwargs.get("batch_id"),
            "success": success,
        },
    )
    def upsert_auto_generated_rules(
        self,
        patterns: List[Dict[str, Any]],
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """LLM에서 생성된 규칙/제약/베스트 프랙티스/예시를 Neo4j에 업서트.

        Delegates to RuleUpsertManager.
        """
        return self._rule_upsert_manager.upsert_auto_generated_rules(patterns, batch_id)

    def get_rules_by_batch_id(self, batch_id: str) -> List[Dict[str, Any]]:
        """Batch ID로 업서트된 Rule 노드 조회."""
        return self._rule_upsert_manager.get_rules_by_batch_id(batch_id)

    @measure_latency(
        "get_formatting_rules_for_query_type",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1] if len(args) > 1 else "all"),
            "result_count": len_if_sized(result),
        },
    )
    def get_formatting_rules_for_query_type(
        self, query_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Return formatting rules for a given query type (or all)."""
        return self.query_executor.execute_with_fallback(
            CypherQueries.GET_FORMATTING_RULES_FOR_QUERY_TYPE,
            params={"query_type": query_type},
            default=[],
        )

    @measure_latency(
        "get_formatting_rules",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "template_type": kwargs.get("template_type", args[1]),
            "result_length": len_if_sized(result),
        },
    )
    def get_formatting_rules(self, template_type: str) -> str:
        """Get formatting rules for a specific template type from Neo4j.

        Args:
            template_type: Template type (e.g., 'eval', 'rewrite', 'query_gen')

        Returns:
            Formatted markdown string containing all rules grouped by category.
        """

        def transform_to_formatted(records: List[Any]) -> str:
            rules_data = [dict(r) for r in records]
            return format_rules(rules_data)

        result = self.query_executor.execute_with_fallback(
            CypherQueries.GET_FORMATTING_RULES,
            params={"template_type": template_type},
            default="",
            transform=transform_to_formatted,
        )
        # When transform is provided that returns str, result will be str
        return str(result) if not isinstance(result, str) else result

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        """특정 batch_id로 생성된 모든 노드 삭제 (롤백).

        Delegates to RuleUpsertManager.
        """
        return self._rule_upsert_manager.rollback_batch(batch_id)

    def close(self) -> None:
        """Close database connections and clean up resources."""
        # Make close() idempotent - only close if not already closed
        if hasattr(self, "_closed") and self._closed:
            return
        
        if self._graph is not None or self._graph_provider is not None:
            close_connections(self._graph, self._graph_finalizer, self._graph_provider)
            self._graph = None
            self._graph_finalizer = None
            self._graph_provider = None
        
        self._closed = True

    @contextmanager
    def graph_session(self) -> Generator[Any, None, None]:
        """동기 Neo4j 세션 헬퍼.

        - _graph가 있으면 동기 세션 반환
        - _graph_provider가 있으면 별도 이벤트 루프로 async 세션을 동기화
        - 모두 없으면 None yield

        Note: Uses getattr() for defensive access to handle test instances
        created via object.__new__() which bypass __init__.
        """
        graph = getattr(self, "_graph", None)
        provider = getattr(self, "_graph_provider", None)
        yield from create_graph_session(graph, provider)

    # ------------------------------------------------------------------
    # Rule mutation helpers (delegates to RuleManager)
    # ------------------------------------------------------------------
    def update_rule(self, rule_id: str, new_text: str) -> None:
        """Update rule text (delegates to RuleManager)."""
        self._rule_manager.update_rule(rule_id, new_text)

    def add_rule(self, query_type: str, rule_text: str) -> str:
        """Add new rule (delegates to RuleManager)."""
        return self._rule_manager.add_rule(query_type, rule_text)

    def delete_rule(self, rule_id: str) -> None:
        """Delete rule (delegates to RuleManager)."""
        self._rule_manager.delete_rule(rule_id)

    def __del__(self) -> None:
        """Destructor to ensure resources are cleaned up."""
        with suppress(Exception):
            self.close()
