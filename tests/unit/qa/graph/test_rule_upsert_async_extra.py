"""Extra tests for RuleUpsertManager async provider branches."""

from __future__ import annotations

from typing import Any, cast

from src.qa.graph.rule_upsert import RuleUpsertManager


class _AsyncSession:
    async def run(
        self,
        _cypher: str,
        **_params: Any,
    ) -> list[dict[str, Any]]:
        return []


class _SessionCtx:
    async def __aenter__(self) -> _AsyncSession:
        return _AsyncSession()

    async def __aexit__(
        self,
        exc_type: Any,
        exc_val: Any,
        exc_tb: Any,
    ) -> None:
        return None


class _FakeProvider:
    def session(self) -> _SessionCtx:
        return _SessionCtx()


def test_upsert_nodes_with_async_provider() -> None:
    provider = _FakeProvider()
    manager = RuleUpsertManager(graph_provider=cast(Any, provider))

    rule = manager._upsert_rule_node(  # noqa: SLF001
        rule_id="r1",
        description="desc",
        type_hint="explanation",
        batch_id="b1",
        timestamp="ts",
    )
    assert rule["created"] is True

    const = manager._upsert_constraint_node(  # noqa: SLF001
        constraint_id="c1",
        description="c",
        rule_id="r1",
        batch_id="b1",
        timestamp="ts",
    )
    assert const["created"] is True
