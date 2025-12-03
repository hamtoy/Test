"""Rule upsert manager for Neo4j knowledge graph.

Provides methods for upserting auto-generated rules, constraints,
best practices, and examples to Neo4j.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.interfaces import GraphProvider
from src.infra.neo4j import SafeDriver
from src.infra.utils import run_async_safely


class RuleUpsertManager:
    """Manages upserting of auto-generated rules to Neo4j.

    Provides methods for creating and updating Rule, Constraint,
    BestPractice, and Example nodes in the knowledge graph.

    Args:
        graph: Optional SafeDriver for sync Neo4j access
        graph_provider: Optional GraphProvider for async Neo4j access
    """

    def __init__(
        self,
        graph: Optional[SafeDriver] = None,
        graph_provider: Optional[GraphProvider] = None,
    ) -> None:
        """Initialize the RuleUpsertManager."""
        self._graph = graph
        self._graph_provider = graph_provider

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

        Returns:
            Dict with keys:
                - success (bool): 성공 여부
                - batch_id (str): 사용된 배치 ID
                - created (Dict): 생성된 노드 수
                - updated (Dict): 갱신된 노드 수
                - errors (List[str]): 오류 목록
        """
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
        """Rule 노드 업서트."""
        check_cypher = "MATCH (r:Rule {id: $id}) RETURN r.batch_id as existing_batch_id"

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
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
                existing = list(session.run(check_cypher, id=rule_id))
                is_new = len(existing) == 0
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

        return run_async_safely(_run())

    def _upsert_constraint_node(
        self,
        constraint_id: str,
        description: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """Constraint 노드 업서트 및 Rule과 연결."""
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
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
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

        return run_async_safely(_run())

    def _upsert_best_practice_node(
        self,
        bp_id: str,
        text: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """BestPractice 노드 업서트 및 Rule과 연결."""
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
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
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

        return run_async_safely(_run())

    def _upsert_example_node(
        self,
        example_id: str,
        before: str,
        after: str,
        rule_id: str,
        batch_id: str,
        timestamp: str,
    ) -> Dict[str, bool]:
        """Example 노드 업서트 및 Rule과 연결."""
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
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
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

        return run_async_safely(_run())

    def get_rules_by_batch_id(self, batch_id: str) -> List[Dict[str, Any]]:
        """특정 batch_id로 생성된 모든 노드 조회 (롤백 전 확인용).

        Args:
            batch_id: 조회할 배치 ID

        Returns:
            해당 batch_id의 모든 노드 정보 리스트
        """
        cypher = """
        MATCH (n)
        WHERE n.batch_id = $batch_id
        RETURN labels(n) as labels, n.id as id, n.created_at as created_at,
               n.updated_at as updated_at, n.auto_generated as auto_generated
        """

        provider = self._graph_provider
        if provider is None:
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
                records = session.run(cypher, batch_id=batch_id)
                return [dict(r) for r in records]

        prov = provider

        async def _run() -> List[Dict[str, Any]]:
            async with prov.session() as session:
                records = await session.run(cypher, batch_id=batch_id)
                return [dict(r) for r in records]

        return run_async_safely(_run())

    def rollback_batch(self, batch_id: str) -> Dict[str, Any]:
        """특정 batch_id로 생성된 모든 노드 삭제 (롤백).

        Args:
            batch_id: 삭제할 배치 ID

        Returns:
            {"success": True, "deleted_count": N}

        Warning:
            이 작업은 되돌릴 수 없습니다. 실행 전 get_rules_by_batch_id()로 확인하세요.
        """
        count_cypher = "MATCH (n) WHERE n.batch_id = $batch_id RETURN count(n) as cnt"
        delete_cypher = "MATCH (n) WHERE n.batch_id = $batch_id DETACH DELETE n"

        provider = self._graph_provider
        if provider is None:
            assert self._graph is not None, (
                "Graph driver must be initialized when provider is None"
            )
            with self._graph.session() as session:
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

        return run_async_safely(_run())
