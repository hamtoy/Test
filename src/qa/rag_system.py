# mypy: disable-error-code=attr-defined
from __future__ import annotations

import asyncio
import logging
import os
import weakref
from collections.abc import Sized
from contextlib import contextmanager, suppress
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional

import google.generativeai as genai
from dotenv import load_dotenv

if TYPE_CHECKING:
    from typing import Protocol

    class Embeddings(Protocol):
        """Protocol for text embedding models."""

        def embed_documents(self, texts: List[str]) -> List[List[float]]:
            """Embed multiple documents.

            Args:
                texts: List of text documents to embed

            Returns:
                List of embedding vectors
            """
            ...

        def embed_query(self, text: str) -> List[float]:
            """Embed a single query text.

            Args:
                text: Query text to embed

            Returns:
                Embedding vector
            """
            ...
else:
    from langchain_core.embeddings import Embeddings
from langchain_core.exceptions import LangChainException
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from checks.validate_session import validate_turns
from src.caching.analytics import CacheMetrics
from src.config import AppConfig
from src.config.utils import require_env
from src.core.factory import get_graph_provider
from src.core.interfaces import GraphProvider
from src.infra.metrics import measure_latency
from src.infra.neo4j import SafeDriver, create_sync_driver
from src.infra.utils import run_async_safely
from src.qa.graph.rule_upsert import RuleUpsertManager

logger = logging.getLogger(__name__)


def _len_if_sized(obj: Any) -> int:
    """Return length if the object supports __len__, else 0."""
    if isinstance(obj, Sized):
        return len(obj)
    return 0


load_dotenv()


class CustomGeminiEmbeddings(Embeddings):
    """Gemini 임베딩 래퍼."""

    def __init__(self, api_key: str, model: str = "models/text-embedding-004") -> None:
        """Initialize the Gemini embeddings wrapper.

        Args:
            api_key: The Google AI API key.
            model: The embedding model name to use.
        """
        genai.configure(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text documents to embed.

        Returns:
            List of embedding vectors.
        """
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text.

        Args:
            text: The query text to embed.

        Returns:
            The embedding vector.
        """
        result = genai.embed_content(
            model=self.model, content=text, task_type="retrieval_query"
        )
        return list(result["embedding"])


class QAKnowledgeGraph:
    """RAG + 그래프 기반 QA 헬퍼.
    - Neo4j 그래프 쿼리
    - (선택) Rule 벡터 검색
    - 세션 구조 검증
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
        self.neo4j_uri: Optional[str] = None
        self.neo4j_user: Optional[str] = None
        self.neo4j_password: Optional[str] = None
        self._vector_store: Any = None
        self._cache_metrics = CacheMetrics(namespace="qa_kg")

        if provider is None:
            self.neo4j_uri = neo4j_uri or require_env("NEO4J_URI")
            self.neo4j_user = neo4j_user or require_env("NEO4J_USER")
            self.neo4j_password = neo4j_password or require_env("NEO4J_PASSWORD")

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
            # enable tests relying on _graph assignment for provider case
            self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI")
            self.neo4j_user = neo4j_user or os.getenv("NEO4J_USER")
            self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
            if self.neo4j_uri and self.neo4j_user and self.neo4j_password:
                self._graph = create_sync_driver(
                    self.neo4j_uri,
                    self.neo4j_user,
                    self.neo4j_password,
                    register_atexit=True,
                    graph_db_factory=GraphDatabase.driver,
                )
                self._graph_finalizer = weakref.finalize(self._graph, self._graph.close)

        self._init_vector_store()

        # Initialize RuleUpsertManager for delegation
        self._rule_upsert_manager = RuleUpsertManager(
            graph=self._graph,
            graph_provider=self._graph_provider,
        )

    def _record_vector_metrics(
        self,
        *,
        query: str,
        k: int,
        result_count: int,
        success: bool,
        duration_ms: float,
    ) -> Dict[str, Any]:
        """Record vector search metrics and return structured log extras."""
        status = "hit" if success else "error"
        self.cache_metrics.record_query(
            "vector_search",
            duration_ms=duration_ms,
            result_count=result_count,
            status=status,
        )
        return {
            "metric": "vector_search",
            "duration_ms": round(duration_ms, 2),
            "k": k,
            "query_length": len(query),
            "result_count": result_count,
        }

    @property
    def cache_metrics(self) -> CacheMetrics:
        """Lazy-initialize cache metrics for cases where __init__ is bypassed in tests."""
        if not hasattr(self, "_cache_metrics") or self._cache_metrics is None:
            self._cache_metrics = CacheMetrics(namespace="qa_kg")
        return self._cache_metrics

    def _init_vector_store(self) -> None:
        """GEMINI_API_KEY로 임베딩을 생성합니다. 키가 없거나 인덱스가 없으면 건너뜀."""
        try:
            from langchain_neo4j import Neo4jVector

            gemini_api_key = os.getenv("GEMINI_API_KEY")

            if not gemini_api_key:
                logger.debug(
                    "GEMINI_API_KEY not set; skipping vector store initialization."
                )
                return

            embedding_model: Any = CustomGeminiEmbeddings(api_key=gemini_api_key)

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
        except ImportError as exc:
            logger.debug(
                "langchain_neo4j not installed; skipping vector store. (%s)", exc
            )
            self._vector_store = None
        except (
            Neo4jError,
            ServiceUnavailable,
            LangChainException,
            ValueError,
        ) as exc:
            logger.warning("Failed to initialize Neo4j vector store: %s", exc)
            self._vector_store = None

    @measure_latency(
        "vector_search",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: args[
            0
        ]._record_vector_metrics(
            query=kwargs.get("query", args[1]),
            k=kwargs.get("k", args[2] if len(args) > 2 else 5),
            result_count=_len_if_sized(result),
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
            "result_count": _len_if_sized(result),
        },
    )
    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """QueryType과 연결된 제약 조건 조회.
        - QueryType-[:HAS_CONSTRAINT]->Constraint 관계 사용
        """
        cypher = """
        MATCH (qt:QueryType {name: $qt})-[:HAS_CONSTRAINT]->(c:Constraint)
        RETURN 
            c.name AS name,
            c.description AS description,
            c.priority AS priority,
            c.category AS category,
            c.applies_to AS applies_to
        ORDER BY c.priority DESC
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
        "get_best_practices",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "query_type": kwargs.get("query_type", args[1]),
            "result_count": _len_if_sized(result),
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
            with self._graph.session() as session:  # type: ignore[union-attr]
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
            "result_count": _len_if_sized(result),
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
            with self._graph.session() as session:  # type: ignore[union-attr]
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
        from scripts.build_session import SessionContext

        turns = session.get("turns", [])
        if not turns:
            return {"ok": False, "issues": ["turns가 비어있습니다."]}

        ctx_kwargs = session.get("context", {})
        try:
            ctx = SessionContext(**ctx_kwargs)
            res = validate_turns([type("T", (), t) for t in turns], ctx)
            return res
        except (TypeError, ValueError) as exc:
            return {"ok": False, "issues": [f"컨텍스트 생성 실패: {exc}"]}
        except (AttributeError, KeyError, RuntimeError) as exc:
            return {"ok": False, "issues": [f"컨텍스트 검증 실패: {exc}"]}

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
            "result_count": _len_if_sized(result),
        },
    )
    def get_formatting_rules_for_query_type(
        self, query_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Return formatting rules for a given query type (or all)."""
        cypher = """
        MATCH (fr:FormattingRule)
        WHERE fr.applies_to = 'all' OR fr.applies_to = $query_type
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
            async with provider.session() as session:
                result = await session.run(cypher, query_type=query_type)
                if hasattr(result, "__aiter__"):
                    records = [record async for record in result]
                else:
                    records = list(result)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    @measure_latency(
        "get_formatting_rules",
        get_extra=lambda args, kwargs, result, success, elapsed_ms: {
            "template_type": kwargs.get("template_type", args[1]),
            "result_length": _len_if_sized(result),
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
                    return self._format_rules(rules_data)
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
                return self._format_rules(rules_data)

        return run_async_safely(_run())

    def _format_rules(self, rules_data: List[Dict[str, Any]]) -> str:
        """Format rules data into markdown structure.

        Args:
            rules_data: List of rule dictionaries with category, text, priority

        Returns:
            Formatted markdown string
        """
        if not rules_data:
            return ""

        # Group rules by category
        categories: Dict[str, List[str]] = {}
        for rule in rules_data:
            category = rule.get("category", "general")
            text = rule.get("text", "")
            if category not in categories:
                categories[category] = []
            categories[category].append(text)

        # Format as markdown
        rules_texts = [rule.get("text", "") for rule in rules_data if rule.get("text")]
        if not rules_texts:
            return ""
        lines = ["### Formatting Rules"]
        lines.extend(f"- {text}" for text in rules_texts)
        return "\n".join(lines)

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

    def __del__(self) -> None:
        """Destructor to ensure resources are cleaned up."""
        with suppress(Exception):
            self.close()


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
