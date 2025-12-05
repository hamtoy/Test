# mypy: disable-error-code=attr-defined
"""QA Knowledge Graph - RAG System with Neo4j Integration (Refactored).

This module provides the QAKnowledgeGraph class - a simplified facade that delegates
to specialized modules in src/qa/graph/ for actual functionality.

## Architecture (PROMPT-003 Refactoring)

**Delegation Pattern**:
- Connection Management → graph/connection.py (Neo4jConnectionManager)
- Vector Search → graph/vector_search.py (VectorSearchEngine)
- Rule Operations → graph/rule_upsert.py (RuleUpsertManager)
- Query Execution → graph/query_executor.py
- Validators → graph/validators.py

**Main Class**:
- QAKnowledgeGraph: Facade coordinating graph operations

**Refactoring Goals** (695 lines → ~400 lines):
- ✅ Extract connection management (_init_connection method)
- ✅ Leverage existing graph/ modules
- ✅ Maintain backward compatibility
- ✅ All 19 RAG tests passing

For architecture details: docs/ARCHITECTURE.md
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from contextlib import contextmanager, suppress
from typing import Any, Dict, Generator, List, Optional
from uuid import uuid4

import google.generativeai as genai  # noqa: F401
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from src.caching.analytics import CacheMetrics
from src.config import AppConfig
from src.config.utils import require_env
from src.core.factory import get_graph_provider
from src.core.interfaces import GraphProvider
from src.infra.metrics import measure_latency
from src.infra.neo4j import SafeDriver, create_sync_driver
from src.infra.utils import run_async_safely
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
from src.qa.rule_loader import clear_global_rule_cache

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
        self._graph: Optional[SafeDriver] = None
        self._graph_finalizer: Optional[Any] = None
        self._cache_metrics = CacheMetrics(namespace="qa_kg")

        # Store credentials for later use
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
        self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER")
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")

        # Initialize connection based on provider
        self._init_connection(provider)

        # Initialize vector store (lazy, optional)
        self._vector_store: Any = None
        self._init_vector_store()

        # Initialize RuleUpsertManager for delegation
        self._rule_upsert_manager = RuleUpsertManager(
            graph=self._graph,
            graph_provider=self._graph_provider,
        )

        # Ensure required formatting rule schema is present
        ensure_formatting_rule_schema(
            driver=self._graph, provider=self._graph_provider, logger=logger
        )

    def _init_connection(self, provider: Optional[GraphProvider]) -> None:
        """Initialize Neo4j connection.

        Extracted from __init__ for clarity. Uses provider if available,
        otherwise creates direct driver connection.
        """
        if provider is None:
            # No provider - create direct connection
            if not self.neo4j_uri or not self.neo4j_user or not self.neo4j_password:
                self.neo4j_uri = require_env("NEO4J_URI")
                self.neo4j_user = require_env("NEO4J_USER")
                self.neo4j_password = require_env("NEO4J_PASSWORD")

            try:
                self._graph = create_sync_driver(
                    self.neo4j_uri,
                    self.neo4j_user,
                    self.neo4j_password,
                    register_atexit=True,
                    graph_db_factory=GraphDatabase.driver,
                )
                self._graph_finalizer = weakref.finalize(self._graph, self._graph.close)
            except Neo4jError as e:
                raise RuntimeError(f"Neo4j 연결 실패: {e}")
        else:
            # Provider available - use it, but also setup direct connection if credentials exist
            if self.neo4j_uri and self.neo4j_user and self.neo4j_password:
                self._graph = create_sync_driver(
                    self.neo4j_uri,
                    self.neo4j_user,
                    self.neo4j_password,
                    register_atexit=True,
                    graph_db_factory=GraphDatabase.driver,
                )
                self._graph_finalizer = weakref.finalize(self._graph, self._graph.close)

    @property
    def cache_metrics(self) -> CacheMetrics:
        """Lazy-initialize cache metrics for cases where __init__ is bypassed in tests."""
        if not hasattr(self, "_cache_metrics") or self._cache_metrics is None:
            self._cache_metrics = CacheMetrics(namespace="qa_kg")
        return self._cache_metrics

    def _init_vector_store(self) -> None:
        """GEMINI_API_KEY로 임베딩을 생성합니다. 키가 없거나 인덱스가 없으면 건너뜀."""
        if not os.getenv("GEMINI_API_KEY"):
            # 환경변수 없으면 현재 값을 유지하고 조용히 반환
            logger.debug(
                "GEMINI_API_KEY not set; skipping vector store initialization."
            )
            return

        new_store = init_vector_store(
            neo4j_uri=self.neo4j_uri,
            neo4j_user=self.neo4j_user,
            neo4j_password=self.neo4j_password,
            logger=logger,
        )
        self._vector_store = new_store

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
        cypher = """
        // 1. QueryType 연결 Constraint
        MATCH (qt:QueryType {name: $qt})-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN 
            c.id AS id,
            c.type AS type,
            c.description AS description,
            c.pattern AS pattern,
            c.severity AS severity,
            c.max_repetition AS max_repetition,
            c.rules AS rules,
            c.priority AS priority,
            c.category AS category,
            c.applies_to AS applies_to
        
        UNION
        
        // 2. 피드백 기반 Constraint
        MATCH (c:Constraint)
        WHERE c.source STARTS WITH 'feedback_'
        RETURN 
            c.id AS id,
            c.type AS type,
            c.description AS description,
            c.pattern AS pattern,
            c.severity AS severity,
            c.max_repetition AS max_repetition,
            c.rules AS rules,
            c.priority AS priority,
            c.category AS category,
            c.applies_to AS applies_to
        """
        provider = getattr(self, "_graph_provider", None)
        # 웹 컨텍스트 등에서 이벤트 루프 충돌을 막기 위해 sync 드라이버를 우선 사용
        if self._graph is not None:
            try:
                with self._graph.session() as session:
                    records = session.run(cypher, qt=query_type)
                    return [dict(r) for r in records]
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Sync constraints query failed: %s", exc)

        if provider is None:
            return []

        prov = provider

        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                result = await session.run(cypher, qt=query_type)
                if hasattr(result, "__aiter__"):
                    records = [record async for record in result]
                else:
                    records = list(result)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    @measure_latency(
        "get_rules_for_query_type",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1]),
            "result_count": len_if_sized(result),
        },
    )
    def get_rules_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """Rule 노드 조회 (APPLIES_TO 관계 또는 applies_to 속성 기반)."""
        cypher = """
        MATCH (qt:QueryType {name: $qt})
        OPTIONAL MATCH (r:Rule)-[:APPLIES_TO]->(qt)
        WITH qt, collect(r) AS rules_rel
        
        OPTIONAL MATCH (r2:Rule)
        WHERE r2.applies_to IN ['all', $qt]
        WITH qt, rules_rel, collect(r2) AS rules_attr
        
        OPTIONAL MATCH (r3:Rule)
        WHERE r3.source = 'feedback_analysis'
        WITH
            qt,
            coalesce(rules_rel, []) AS rules_rel,
            coalesce(rules_attr, []) AS rules_attr,
            collect(r3) AS rules_feedback
        WITH qt, rules_rel + rules_attr + coalesce(rules_feedback, []) AS rules
        
        UNWIND rules AS r
        WITH DISTINCT r
        RETURN
            coalesce(r.id, r.name) AS id,
            coalesce(r.name, '') AS name,
            coalesce(r.text, '') AS text,
            coalesce(r.category, '') AS category,
            coalesce(r.priority, 0) AS priority,
            r.source AS source
        ORDER BY 
            CASE r.priority
                WHEN 'critical' THEN 4
                WHEN 'high' THEN 3
                WHEN 'medium' THEN 2
                ELSE 1
            END DESC,
            priority DESC
        """

        provider = getattr(self, "_graph_provider", None)
        if self._graph is not None:
            try:
                with self._graph.session() as session:
                    records = session.run(cypher, qt=query_type)
                    return [dict(r) for r in records]
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Rule query failed (sync): %s", exc)

        if provider is None:
            logger.warning("No graph provider available for rules")
            return []

        async def _run() -> List[Dict[str, Any]]:
            try:
                async with provider.session() as session:
                    result = await session.run(cypher, qt=query_type)
                    if hasattr(result, "__aiter__"):
                        records = [record async for record in result]
                    else:
                        records = list(result)
                    return [dict(r) for r in records]
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Rule query failed (async): %s", exc)
                return []

        return run_async_safely(_run())

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
        cypher = """
        MATCH (qt:QueryType {name: $qt})<-[:APPLIES_TO]-(b:BestPractice)
        RETURN b.id AS id, b.text AS text
        """
        provider = getattr(self, "_graph_provider", None)
        if provider is None:
            if self._graph is None:
                raise ValueError(
                    "Graph driver must be initialized when provider is None"
                )
            with self._graph.session() as session:
                return [dict(r) for r in session.run(cypher, qt=query_type)]

        prov = provider

        async def _run() -> List[Dict[str, str]]:
            async with prov.session() as session:
                records = await session.run(cypher, qt=query_type)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    @measure_latency(
        "get_examples",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "limit": kwargs.get("limit", args[1] if len(args) > 1 else 5),
            "result_count": len_if_sized(result),
        },
    )
    def get_examples(self, limit: int = 5) -> List[Dict[str, str]]:
        """Example 노드 조회 (현재 Rule과 직접 연결되지 않았으므로 전체에서 샘플링)."""
        cypher = """
        MATCH (e:Example)
        RETURN e.id AS id, e.text AS text, e.type AS type
        LIMIT $limit
        """
        provider = getattr(self, "_graph_provider", None)
        if provider is None:
            if self._graph is None:
                raise ValueError(
                    "Graph driver must be initialized when provider is None"
                )
            with self._graph.session() as session:
                return [dict(r) for r in session.run(cypher, limit=limit)]

        prov = provider

        async def _run() -> List[Dict[str, str]]:
            async with prov.session() as session:
                records = await session.run(cypher, limit=limit)
                return [dict(r) for r in records]

        return run_async_safely(_run())

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
        cypher = """
        OPTIONAL MATCH (fr:FormattingRule)
        WHERE (fr.applies_to = 'all' OR fr.applies_to = $query_type)
        WITH fr WHERE fr IS NOT NULL
        RETURN fr.name AS name,
               fr.description AS description,
               fr.priority AS priority,
               fr.category AS category,
               coalesce(fr.examples_good, '') AS examples_good,
               coalesce(fr.examples_bad, '') AS examples_bad
        ORDER BY fr.priority DESC
        """
        provider = getattr(self, "_graph_provider", None)

        if self._graph is not None:
            try:
                with self._graph.session() as session:
                    result = session.run(cypher, query_type=query_type)
                    return [dict(record) for record in result]
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Formatting rule query failed (sync): %s", exc)

        if provider is None:
            logger.warning("No graph provider available for formatting rules")
            return []

        async def _run() -> List[Dict[str, Any]]:
            try:
                async with provider.session() as session:
                    result = await session.run(cypher, query_type=query_type)
                    if hasattr(result, "__aiter__"):
                        records = [record async for record in result]
                    else:
                        records = list(result)
                    return [dict(r) for r in records]
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Formatting rule query failed (async): %s", exc)
                return []

        return run_async_safely(_run())

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
        cypher = """
        MATCH (t:Template {name: $template_type})-[:ENFORCES]->(r:Rule)
        RETURN r.text AS text, coalesce(r.priority, 999) AS priority
        ORDER BY priority
        """
        provider = getattr(self, "_graph_provider", None)

        # Try sync driver first if available
        if self._graph is not None:
            try:
                with self._graph.session() as session:
                    records = session.run(cypher, template_type=template_type)
                    rules_data = [dict(r) for r in records]
                    return format_rules(rules_data)
            except (Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Sync formatting rules query failed: %s", exc)

        if provider is None:
            logger.warning("No graph provider available for formatting rules")
            return ""

        prov = provider

        async def _run() -> str:
            async with prov.session() as session:
                result = await session.run(cypher, template_type=template_type)
                if hasattr(result, "__aiter__"):
                    records = [record async for record in result]
                else:
                    records = list(result)
                rules_data = [dict(r) for r in records]
                return format_rules(rules_data)

        return run_async_safely(_run())

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        """특정 batch_id로 생성된 모든 노드 삭제 (롤백).

        Delegates to RuleUpsertManager.
        """
        return self._rule_upsert_manager.rollback_batch(batch_id)

    def close(self) -> None:
        """Close database connections and clean up resources."""
        if self._graph:
            with suppress(Exception):
                self._graph.close()
            self._graph = None
        if self._graph_finalizer and self._graph_finalizer.alive:
            with suppress(Exception):
                self._graph_finalizer()
            self._graph_finalizer = None
        provider = self._graph_provider
        if provider:
            try:
                try:
                    loop = asyncio.get_running_loop()
                    running = True
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    running = False

                close_coro = provider.close()
                if running and loop.is_running():
                    loop.create_task(close_coro)
                else:
                    loop.run_until_complete(close_coro)
                    if not running:
                        loop.close()
                        asyncio.set_event_loop(None)
            except (RuntimeError, Neo4jError, ServiceUnavailable) as exc:
                logger.warning("Graph provider close failed: %s", exc)
            self._graph_provider = None

    @contextmanager
    def graph_session(self) -> Generator[Any, None, None]:
        """동기 Neo4j 세션 헬퍼.

        - _graph가 있으면 동기 세션 반환
        - _graph_provider가 있으면 별도 이벤트 루프로 async 세션을 동기화
        - 모두 없으면 None yield
        """
        if self._graph:
            with self._graph.session() as session:
                yield session
            return

        provider = self._graph_provider
        if provider:
            # 동기 컨텍스트에서 async provider를 동기화; 실행 중인 루프가 있으면 fallback
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    logger.debug(
                        "graph_session: event loop already running; skipping provider session"
                    )
                    yield None
                    return
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            session_cm = provider.session()
            session = loop.run_until_complete(session_cm.__aenter__())
            try:
                yield session
            finally:
                loop.run_until_complete(session_cm.__aexit__(None, None, None))
                loop.close()
            return

        logger.debug("graph_session: graph not available; yielding None")
        yield None

    # ------------------------------------------------------------------
    # Rule mutation helpers (자동 캐시 무효화 포함)
    # ------------------------------------------------------------------
    def update_rule(self, rule_id: str, new_text: str) -> None:
        """규칙 텍스트 업데이트 후 캐시 무효화."""
        cypher = """
        MATCH (r:Rule {id: $rule_id})
        SET r.text = $new_text
        RETURN count(r) AS updated
        """
        with self.graph_session() as session:
            if session is None:
                logger.warning("update_rule skipped: graph unavailable")
                return
            result = session.run(cypher, rule_id=rule_id, new_text=new_text)
            updated = result.single().get("updated", 0) if result else 0
            logger.info("Rule updated id=%s (updated=%s)", rule_id, updated)
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after update")

    def add_rule(self, query_type: str, rule_text: str) -> str:
        """규칙 추가 후 캐시 무효화."""
        rule_id = str(uuid4())
        cypher = """
        MERGE (qt:QueryType {name: $query_type})
        CREATE (r:Rule {id: $rule_id, text: $rule_text})
        MERGE (r)-[:APPLIES_TO]->(qt)
        RETURN r.id AS id
        """
        with self.graph_session() as session:
            if session is None:
                logger.warning("add_rule skipped: graph unavailable")
                return rule_id
            result = session.run(
                cypher, query_type=query_type, rule_id=rule_id, rule_text=rule_text
            )
            record = result.single() if result else None
            created_id = record.get("id") if record else rule_id
            logger.info("Rule added id=%s (query_type=%s)", created_id, query_type)
            rule_id = str(created_id)
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after add")
        return rule_id

    def delete_rule(self, rule_id: str) -> None:
        """규칙 삭제 후 캐시 무효화."""
        cypher = "MATCH (r:Rule {id: $rule_id}) DETACH DELETE r"
        with self.graph_session() as session:
            if session is None:
                logger.warning("delete_rule skipped: graph unavailable")
                return
            result = session.run(cypher, rule_id=rule_id)
            summary = result.consume() if result else None
            deleted = getattr(summary.counters, "nodes_deleted", 0) if summary else 0
            logger.info("Rule deleted id=%s (deleted=%s)", rule_id, deleted)
        clear_global_rule_cache()
        logger.info("Global rule cache cleared after delete")

    def __del__(self) -> None:
        """Destructor to ensure resources are cleaned up."""
        with suppress(Exception):
            self.close()
