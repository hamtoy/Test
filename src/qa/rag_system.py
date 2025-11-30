from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import time
import weakref
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
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

    def _init_vector_store(self) -> None:
        """GEMINI_API_KEY로 임베딩을 생성합니다. 키가 없거나 인덱스가 없으면 건너뜀.
        """
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
        """Example 노드 조회 (현재 Rule과 직접 연결되지 않았으므로 전체에서 샘플링).
        """
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
        """checks/validate_session 로직을 활용해 세션 구조 검증.
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
        except (TypeError, ValueError) as exc:
            return {"ok": False, "issues": [f"컨텍스트 생성 실패: {exc}"]}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "issues": [f"컨텍스트 검증 실패: {exc}"]}

    # =========================================================================
    # 자동 생성 규칙/제약/베스트 프랙티스/예시 업서트(Upsert) 함수
    # =========================================================================
    #
    # 입력 형식 예시 (LLM에서 반환된 패턴 리스트):
    # {
    #   "patterns": [
    #     {
    #       "id": "rule_001",
    #       "rule": "설명문에서 표/그래프 참조 금지",
    #       "type_hint": "explanation",
    #       "constraint": "표/그래프를 인용하면 안 됨",
    #       "best_practice": "본문 텍스트만 인용",
    #       "example_before": "표에 따르면 A는 100이다",
    #       "example_after": "A는 100이다"
    #     },
    #     ...
    #   ]
    # }
    #
    # 출력 형식 예시:
    # {
    #   "success": True,
    #   "batch_id": "batch_20240101_120000",
    #   "created": {"rules": 2, "constraints": 1, "best_practices": 1, "examples": 1},
    #   "updated": {"rules": 0, "constraints": 0, "best_practices": 0, "examples": 0},
    #   "errors": []
    # }
    # =========================================================================

    def upsert_auto_generated_rules(
        self,
        patterns: List[Dict[str, Any]],
        batch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """LLM에서 생성된 규칙/제약/베스트 프랙티스/예시를 Neo4j에 업서트.

        Args:
            patterns: LLM에서 반환된 패턴 리스트. 각 패턴은 다음 필드를 가짐:
                - id (str): 규칙의 고유 ID
                - rule (str): 규칙 설명 텍스트
                - type_hint (str): 질의 유형 힌트 (예: 'explanation', 'summary')
                - constraint (str, optional): 제약 조건 텍스트
                - best_practice (str, optional): 베스트 프랙티스 텍스트
                - example_before (str, optional): 수정 전 예시
                - example_after (str, optional): 수정 후 예시
            batch_id: 배치 ID. 미지정 시 자동 생성됨.
                      동일 ID의 노드가 존재하고 batch_id가 다르면 새 버전으로 추가.
                      batch_id가 같으면 기존 노드 갱신(update).

        Returns:
            Dict with keys:
                - success (bool): 성공 여부
                - batch_id (str): 사용된 배치 ID
                - created (Dict): 생성된 노드 수 (rules, constraints, best_practices, examples)
                - updated (Dict): 갱신된 노드 수
                - errors (List[str]): 오류 목록

        Example:
            >>> kg = QAKnowledgeGraph()
            >>> result = kg.upsert_auto_generated_rules([
            ...     {
            ...         "id": "rule_001",
            ...         "rule": "설명문에서 표 참조 금지",
            ...         "type_hint": "explanation",
            ...         "constraint": "표/그래프 인용 불가",
            ...         "best_practice": "본문 텍스트만 인용",
            ...         "example_before": "표에 따르면...",
            ...         "example_after": "본문에 따르면..."
            ...     }
            ... ], batch_id="batch_v1")
            >>> print(result)
            {'success': True, 'batch_id': 'batch_v1', 'created': {...}, ...}

        Rollback Query Example:
            # batch_id로 생성된 모든 노드 조회
            MATCH (n) WHERE n.batch_id = "batch_v1" RETURN n

            # batch_id로 일괄 삭제 (롤백)
            MATCH (n) WHERE n.batch_id = "batch_v1" DETACH DELETE n
        """
        # 배치 ID 자동 생성
        if batch_id is None:
            batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        result: Dict[str, Any] = {
            "success": True,
            "batch_id": batch_id,
            "created": {
                "rules": 0,
                "constraints": 0,
                "best_practices": 0,
                "examples": 0,
            },
            "updated": {
                "rules": 0,
                "constraints": 0,
                "best_practices": 0,
                "examples": 0,
            },
            "errors": [],
        }

        timestamp = datetime.now(timezone.utc).isoformat()

        for pattern in patterns:
            try:
                # 필수 필드 검증
                rule_id = pattern.get("id")
                rule_text = pattern.get("rule")
                type_hint = pattern.get("type_hint")

                if not rule_id or not rule_text:
                    result["errors"].append(f"패턴에 id/rule 필드가 없음: {pattern}")
                    continue

                # 1. Rule 노드 업서트
                rule_result = self._upsert_rule_node(
                    rule_id=rule_id,
                    description=rule_text,
                    type_hint=type_hint or "",
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                if rule_result["created"]:
                    result["created"]["rules"] += 1
                else:
                    result["updated"]["rules"] += 1

                # 2. Constraint 노드 업서트 (있는 경우)
                constraint_text = pattern.get("constraint")
                if constraint_text:
                    constraint_id = f"{rule_id}_constraint"
                    const_result = self._upsert_constraint_node(
                        constraint_id=constraint_id,
                        description=constraint_text,
                        rule_id=rule_id,
                        batch_id=batch_id,
                        timestamp=timestamp,
                    )
                    if const_result["created"]:
                        result["created"]["constraints"] += 1
                    else:
                        result["updated"]["constraints"] += 1

                # 3. BestPractice 노드 업서트 (있는 경우)
                best_practice_text = pattern.get("best_practice")
                if best_practice_text:
                    bp_id = f"{rule_id}_bestpractice"
                    bp_result = self._upsert_best_practice_node(
                        bp_id=bp_id,
                        text=best_practice_text,
                        rule_id=rule_id,
                        batch_id=batch_id,
                        timestamp=timestamp,
                    )
                    if bp_result["created"]:
                        result["created"]["best_practices"] += 1
                    else:
                        result["updated"]["best_practices"] += 1

                # 4. Example 노드 업서트 (before/after가 있는 경우)
                example_before = pattern.get("example_before")
                example_after = pattern.get("example_after")
                if example_before or example_after:
                    example_id = f"{rule_id}_example"
                    ex_result = self._upsert_example_node(
                        example_id=example_id,
                        before=example_before or "",
                        after=example_after or "",
                        rule_id=rule_id,
                        batch_id=batch_id,
                        timestamp=timestamp,
                    )
                    if ex_result["created"]:
                        result["created"]["examples"] += 1
                    else:
                        result["updated"]["examples"] += 1

            except Exception as exc:  # noqa: BLE001
                result["errors"].append(
                    f"패턴 처리 중 오류 ({pattern.get('id', 'unknown')}): {exc}"
                )
                result["success"] = False

        return result

    def _upsert_rule_node(
        self,
        rule_id: str,
        description: str,
        type_hint: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """Rule 노드 업서트.

        노드 속성:
            - id: 규칙 고유 ID
            - description: 규칙 설명
            - type_hint: 질의 유형 힌트
            - batch_id: 배치 ID (롤백용)
            - created_at: 생성 시각
            - updated_at: 갱신 시각
            - auto_generated: True (자동 생성 표시)
            - level: 'soft' (소프트 규칙)

        Cypher 예시:
            MERGE (r:Rule {id: $id})
            ON CREATE SET r.description = $desc, r.auto_generated = true, ...
            ON MATCH SET r.description = $desc, r.updated_at = $ts, ...

        Returns:
            {"created": True/False} - True면 새로 생성됨
        """
        # 먼저 노드 존재 여부 확인
        check_cypher = "MATCH (r:Rule {id: $id}) RETURN r.batch_id as existing_batch_id"

        # 업서트 Cypher: 동일 id가 존재하면 갱신, 없으면 생성
        upsert_cypher = """
        MERGE (r:Rule {id: $id})
        ON CREATE SET
            r.description = $description,
            r.type_hint = $type_hint,
            r.batch_id = $batch_id,
            r.created_at = $timestamp,
            r.updated_at = $timestamp,
            r.auto_generated = true,
            r.level = 'soft'
        ON MATCH SET
            r.description = $description,
            r.type_hint = $type_hint,
            r.batch_id = $batch_id,
            r.updated_at = $timestamp
        """

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                # 존재 여부 확인
                existing = list(session.run(check_cypher, id=rule_id))
                is_new = len(existing) == 0

                # 업서트 실행
                session.run(
                    upsert_cypher,
                    id=rule_id,
                    description=description,
                    type_hint=type_hint,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        prov = provider

        async def _run() -> Dict[str, bool]:
            async with prov.session() as session:
                existing = await session.run(check_cypher, id=rule_id)
                existing_list = (
                    [r async for r in existing]
                    if hasattr(existing, "__aiter__")
                    else list(existing)
                )
                is_new = len(existing_list) == 0

                await session.run(
                    upsert_cypher,
                    id=rule_id,
                    description=description,
                    type_hint=type_hint,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        return _run_async_safely(_run())

    def _upsert_constraint_node(
        self,
        constraint_id: str,
        description: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """Constraint 노드 업서트 및 Rule과 연결.

        노드 속성:
            - id: 제약 고유 ID
            - description: 제약 설명
            - batch_id: 배치 ID
            - created_at / updated_at: 시각
            - auto_generated: True

        관계:
            (Rule)-[:ENFORCES]->(Constraint)

        Cypher 예시:
            MERGE (c:Constraint {id: $id})
            ON CREATE SET c.description = $desc, ...
            WITH c
            MATCH (r:Rule {id: $rule_id})
            MERGE (r)-[:ENFORCES]->(c)
        """
        check_cypher = "MATCH (c:Constraint {id: $id}) RETURN c.batch_id"

        upsert_cypher = """
        MERGE (c:Constraint {id: $id})
        ON CREATE SET
            c.description = $description,
            c.batch_id = $batch_id,
            c.created_at = $timestamp,
            c.updated_at = $timestamp,
            c.auto_generated = true
        ON MATCH SET
            c.description = $description,
            c.batch_id = $batch_id,
            c.updated_at = $timestamp
        WITH c
        MATCH (r:Rule {id: $rule_id})
        MERGE (r)-[:ENFORCES]->(c)
        """

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                existing = list(session.run(check_cypher, id=constraint_id))
                is_new = len(existing) == 0
                session.run(
                    upsert_cypher,
                    id=constraint_id,
                    description=description,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        prov = provider

        async def _run() -> Dict[str, bool]:
            async with prov.session() as session:
                existing = await session.run(check_cypher, id=constraint_id)
                existing_list = (
                    [r async for r in existing]
                    if hasattr(existing, "__aiter__")
                    else list(existing)
                )
                is_new = len(existing_list) == 0
                await session.run(
                    upsert_cypher,
                    id=constraint_id,
                    description=description,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        return _run_async_safely(_run())

    def _upsert_best_practice_node(
        self,
        bp_id: str,
        text: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """BestPractice 노드 업서트 및 Rule과 연결.

        노드 속성:
            - id: 베스트 프랙티스 고유 ID
            - text: 베스트 프랙티스 내용
            - batch_id: 배치 ID
            - created_at / updated_at: 시각
            - auto_generated: True

        관계:
            (Rule)-[:RECOMMENDS]->(BestPractice)

        Cypher 예시:
            MERGE (b:BestPractice {id: $id})
            ON CREATE SET b.text = $text, ...
            WITH b
            MATCH (r:Rule {id: $rule_id})
            MERGE (r)-[:RECOMMENDS]->(b)
        """
        check_cypher = "MATCH (b:BestPractice {id: $id}) RETURN b.batch_id"

        upsert_cypher = """
        MERGE (b:BestPractice {id: $id})
        ON CREATE SET
            b.text = $text,
            b.batch_id = $batch_id,
            b.created_at = $timestamp,
            b.updated_at = $timestamp,
            b.auto_generated = true
        ON MATCH SET
            b.text = $text,
            b.batch_id = $batch_id,
            b.updated_at = $timestamp
        WITH b
        MATCH (r:Rule {id: $rule_id})
        MERGE (r)-[:RECOMMENDS]->(b)
        """

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                existing = list(session.run(check_cypher, id=bp_id))
                is_new = len(existing) == 0
                session.run(
                    upsert_cypher,
                    id=bp_id,
                    text=text,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        prov = provider

        async def _run() -> Dict[str, bool]:
            async with prov.session() as session:
                existing = await session.run(check_cypher, id=bp_id)
                existing_list = (
                    [r async for r in existing]
                    if hasattr(existing, "__aiter__")
                    else list(existing)
                )
                is_new = len(existing_list) == 0
                await session.run(
                    upsert_cypher,
                    id=bp_id,
                    text=text,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        return _run_async_safely(_run())

    def _upsert_example_node(
        self,
        example_id: str,
        before: str,
        after: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """Example 노드 업서트 및 Rule과 연결.

        노드 속성:
            - id: 예시 고유 ID
            - before: 수정 전 예시 텍스트
            - after: 수정 후 예시 텍스트
            - batch_id: 배치 ID
            - created_at / updated_at: 시각
            - auto_generated: True

        관계:
            (Example)-[:DEMONSTRATES]->(Rule)

        Cypher 예시:
            MERGE (e:Example {id: $id})
            ON CREATE SET e.before = $before, e.after = $after, ...
            WITH e
            MATCH (r:Rule {id: $rule_id})
            MERGE (e)-[:DEMONSTRATES]->(r)
        """
        check_cypher = "MATCH (e:Example {id: $id}) RETURN e.batch_id"

        upsert_cypher = """
        MERGE (e:Example {id: $id})
        ON CREATE SET
            e.before = $before,
            e.after = $after,
            e.batch_id = $batch_id,
            e.created_at = $timestamp,
            e.updated_at = $timestamp,
            e.auto_generated = true
        ON MATCH SET
            e.before = $before,
            e.after = $after,
            e.batch_id = $batch_id,
            e.updated_at = $timestamp
        WITH e
        MATCH (r:Rule {id: $rule_id})
        MERGE (e)-[:DEMONSTRATES]->(r)
        """

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                existing = list(session.run(check_cypher, id=example_id))
                is_new = len(existing) == 0
                session.run(
                    upsert_cypher,
                    id=example_id,
                    before=before,
                    after=after,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        prov = provider

        async def _run() -> Dict[str, bool]:
            async with prov.session() as session:
                existing = await session.run(check_cypher, id=example_id)
                existing_list = (
                    [r async for r in existing]
                    if hasattr(existing, "__aiter__")
                    else list(existing)
                )
                is_new = len(existing_list) == 0
                await session.run(
                    upsert_cypher,
                    id=example_id,
                    before=before,
                    after=after,
                    rule_id=rule_id,
                    batch_id=batch_id,
                    timestamp=timestamp,
                )
                return {"created": is_new}

        return _run_async_safely(_run())

    def get_rules_by_batch_id(self, batch_id: str) -> List[Dict[str, Any]]:
        """특정 batch_id로 생성된 모든 노드 조회 (롤백 전 확인용).

        Args:
            batch_id: 조회할 배치 ID

        Returns:
            해당 batch_id의 모든 노드 정보 리스트

        Example:
            >>> nodes = kg.get_rules_by_batch_id("batch_v1")
            >>> for node in nodes:
            ...     print(f"{node['labels']}: {node['id']}")

        Cypher 예시:
            MATCH (n) WHERE n.batch_id = $batch_id
            RETURN labels(n) as labels, n.id as id, n.created_at as created_at
        """
        cypher = """
        MATCH (n)
        WHERE n.batch_id = $batch_id
        RETURN labels(n) as labels, n.id as id, n.created_at as created_at,
               n.updated_at as updated_at, n.auto_generated as auto_generated
        """

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                records = session.run(cypher, batch_id=batch_id)
                return [dict(r) for r in records]

        prov = provider

        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, batch_id=batch_id)
                return [dict(r) for r in records]

        return _run_async_safely(_run())

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        """특정 batch_id로 생성된 모든 노드 삭제 (롤백).

        Args:
            batch_id: 삭제할 배치 ID

        Returns:
            {"success": True, "deleted_count": N}

        Warning:
            이 작업은 되돌릴 수 없습니다. 실행 전 get_rules_by_batch_id()로 확인하세요.

        Cypher 예시:
            MATCH (n) WHERE n.batch_id = $batch_id DETACH DELETE n
        """
        # 먼저 삭제될 노드 수 확인
        count_cypher = "MATCH (n) WHERE n.batch_id = $batch_id RETURN count(n) as cnt"
        delete_cypher = "MATCH (n) WHERE n.batch_id = $batch_id DETACH DELETE n"

        provider = self._graph_provider
        if provider is None:
            with self._graph.session() as session:  # type: ignore[union-attr]
                count_result = list(session.run(count_cypher, batch_id=batch_id))
                count = count_result[0]["cnt"] if count_result else 0
                session.run(delete_cypher, batch_id=batch_id)
                return {"success": True, "deleted_count": count}

        prov = provider

        async def _run() -> Dict[str, Any]:
            async with prov.session() as session:
                count_result = await session.run(count_cypher, batch_id=batch_id)
                count_list = (
                    [r async for r in count_result]
                    if hasattr(count_result, "__aiter__")
                    else list(count_result)
                )
                count = count_list[0]["cnt"] if count_list else 0
                await session.run(delete_cypher, batch_id=batch_id)
                return {"success": True, "deleted_count": count}

        return _run_async_safely(_run())

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
