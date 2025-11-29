import asyncio

from src.qa.rag_system import QAKnowledgeGraph
from src.core.interfaces import GraphProvider
from typing import Any


class _SyncSession:
    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return False

    def run(self, *args: Any, **kwargs: Any) -> Any:
        return [{"ok": True, "args": args, "kwargs": kwargs}]


class _SyncGraph:
    def session(self) -> Any:
        return _SyncSession()


class _AsyncSession:
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        return [{"ok": True, "args": args, "kwargs": kwargs}]


class _AsyncProvider(GraphProvider):
    def session(self) -> Any:
        class _CM:
            async def __aenter__(self) -> Any:
                return _AsyncSession()

            async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
                return False

        return _CM()

    async def close(self) -> Any:
        return None

    async def verify_connectivity(self) -> Any:
        return None

    async def create_nodes(
        self,
        nodes: Any,
        label: Any,
        merge_on: Any="id",
        merge_keys: Any=None,
    ) -> Any:
        return len(nodes)

    async def create_relationships(
        self,
        rels: Any,
        rel_type: Any,
        from_label: Any,
        to_label: Any,
        from_key: Any="id",
        to_key: Any="id",
    ) -> Any:
        return len(rels)


def test_graph_session_with_sync_graph() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _SyncGraph()  # type: ignore[assignment]
    with kg.graph_session() as session:
        assert session is not None
        assert session.run("RETURN 1")[0]["ok"] is True


def test_graph_session_with_async_provider() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = None
    kg._graph_provider = _AsyncProvider()
    with kg.graph_session() as session:
        # provider path yields async session proxied via sync helper
        assert session is not None
        # run is async in this stub; ensure callable exists
        assert asyncio.iscoroutinefunction(session.run)


def test_graph_session_without_graph() -> None:
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = None
    kg._graph_provider = None
    with kg.graph_session() as session:
        assert session is None
