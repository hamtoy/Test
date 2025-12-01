from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
import weakref
from contextlib import contextmanager, suppress
from typing import (
    Any,
    Coroutine,
    Dict,
    Generator,
    List,
    Optional,
    TypeVar,
)

import google.generativeai as genai
from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from langchain_core.embeddings import Embeddings

from checks.validate_session import validate_turns
from src.core.interfaces import GraphProvider
from src.core.factory import get_graph_provider
from src.config import AppConfig
from src.infra.neo4j import SafeDriver, create_sync_driver
from src.qa.graph.rule_upsert import RuleUpsertManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from sync context, handling the case where
    an event loop is already running.

    If there's already a running event loop (e.g., called from async context),
    run the coroutine in a separate thread to avoid "event loop already running" error.

    Note: This follows the same pattern as close() in this module.
    Setting event loop to None after loop.close() is intentional to clean up
    thread-local state. For the thread case, this only affects the worker thread.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop, create one and run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    # Loop is already running - run in a separate thread
    def run_in_thread() -> T:
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run_in_thread)
        return future.result()


load_dotenv()


def require_env(var: str) -> str:
    val = os.getenv(var)
    if not val:
        raise EnvironmentError(f"환경 변수 {var}가 설정되지 않았습니다 (.env 확인).")
    return val


class CustomGeminiEmbeddings(Embeddings):
    """Gemini 임베딩 래퍼."""

    def __init__(self, api_key: str, model: str = "models/text-embedding-004") -> None:
        genai.configure(api_key=api_key)  # type: ignore[attr-defined]
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        result = genai.embed_content(  # type: ignore[attr-defined]
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
        cfg = config or AppConfig()
        provider = (
            graph_provider if graph_provider is not None else get_graph_provider(cfg)
        )
        self._graph_provider: Optional[GraphProvider] = provider
        self._graph: Optional[SafeDriver] = None
        self._graph_finalizer: Optional[weakref.finalize[..., SafeDriver]] = None
        self.neo4j_uri: Optional[str] = None
        self.neo4j_user: Optional[str] = None
        self.neo4j_password: Optional[str] = None
        self._vector_store: Any = None

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

    def _init_vector_store(self) -> None:
        """GEMINI_API_KEY로 임베딩을 생성합니다. 키가 없거나 인덱스가 없으면 건너뜀."""
        try:
            from langchain_neo4j import Neo4jVector

            gemini_api_key = os.getenv("GEMINI_API_KEY")

            if not gemini_api_key:
                logger.debug("GEMINI_API_KEY 미설정: 벡터 검색을 건너뜁니다.")
                return

            embedding_model = CustomGeminiEmbeddings(api_key=gemini_api_key)

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
        except Exception as e:  # noqa: BLE001
            logger.warning("Neo4j 벡터 스토어 초기화 실패: %s", e)
            self._vector_store = None

    def find_relevant_rules(self, query: str, k: int = 5) -> List[str]:
        """벡터 검색 기반 규칙 찾기 (가능할 때만)."""
        if not self._vector_store:
            return []
        start = time.perf_counter()
        results = self._vector_store.similarity_search(query, k=k)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info("vector_search_ms=%.2f k=%s query=%s", elapsed_ms, k, query)
        return [doc.page_content for doc in results]

    def get_constraints_for_query_type(self, query_type: str) -> List[Dict[str, Any]]:
        """QueryType과 연결된 제약 조건 조회.
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
        RETURN DISTINCT
            c.id AS id,
            c.description AS description,
            c.type AS type,
            c.pattern AS pattern
        """
        provider = getattr(self, "_graph_provider", None)
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                records = session.run(cypher, qt=query_type)
                return [dict(r) for r in records]

        prov = provider

        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, qt=query_type)
                return [dict(r) for r in records]

        return _run_async_safely(_run())

    def get_best_practices(self, query_type: str) -> List[Dict[str, str]]:
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

        return _run_async_safely(_run())

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

        return _run_async_safely(_run())

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
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "issues": [f"컨텍스트 검증 실패: {exc}"]}

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
        """특정 batch_id로 생성된 모든 노드 조회.

        Delegates to RuleUpsertManager.
        """
        return self._rule_upsert_manager.get_rules_by_batch_id(batch_id)

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        """특정 batch_id로 생성된 모든 노드 삭제 (롤백).

        Delegates to RuleUpsertManager.
        """
        return self._rule_upsert_manager.rollback_batch(batch_id)

    def close(self) -> None:
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
            except Exception:
                pass
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
