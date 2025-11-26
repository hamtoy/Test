import asyncio

from src.qa.rag_system import QAKnowledgeGraph
from src.core.interfaces import GraphProvider


class _SyncSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *args, **kwargs):
        return [{"ok": True, "args": args, "kwargs": kwargs}]


class _SyncGraph:
    def session(self):
        return _SyncSession()


class _AsyncSession:
    async def run(self, *args, **kwargs):
        return [{"ok": True, "args": args, "kwargs": kwargs}]


class _AsyncProvider(GraphProvider):
    def session(self):
        class _CM:
            async def __aenter__(self):
                return _AsyncSession()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        return _CM()

    async def close(self):
        return None

    async def verify_connectivity(self):
        return None


def test_graph_session_with_sync_graph():
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _SyncGraph()
    with kg.graph_session() as session:
        assert session is not None
        assert session.run("RETURN 1")[0]["ok"] is True


def test_graph_session_with_async_provider():
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = None
    kg._graph_provider = _AsyncProvider()
    with kg.graph_session() as session:
        # provider path yields async session proxied via sync helper
        assert session is not None
        # run is async in this stub; ensure callable exists
        assert asyncio.iscoroutinefunction(session.run)


def test_graph_session_without_graph():
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = None
    kg._graph_provider = None
    with kg.graph_session() as session:
        assert session is None
