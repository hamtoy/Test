import asyncio
import json
import os
import sys
import types

import pytest

# Ensure required env is present for AppConfig during import
os.environ.setdefault("GEMINI_API_KEY", "AIza" + "0" * 35)

from src.infra import budget as budget_tracker
from src.qa import rag_system as qa_rag_system
from src.infra import worker


def test_budget_tracker_stats_and_budget():
    tracker = budget_tracker.BudgetTracker(budget_limit_usd=0.01)
    rec = tracker.record_usage(
        {"prompt_tokens": 1000, "completion_tokens": 500, "cached_input_tokens": 250},
        timestamp="now",
        metadata={"m": 1},
    )

    assert rec.total_tokens == 1500
    assert tracker.total_cost_usd > 0
    stats = tracker.get_statistics()
    assert stats["total_calls"] == 1
    assert tracker.is_budget_exceeded(threshold=0.0001) is True


def test_budget_tracker_zero_budget():
    tracker = budget_tracker.BudgetTracker(budget_limit_usd=0.0)
    tracker.record_usage({"prompt_tokens": 0, "completion_tokens": 0})
    assert tracker.get_budget_usage_percent() == 0.0
    assert tracker.is_budget_exceeded() is False


def test_require_env_missing(monkeypatch):
    monkeypatch.delenv("SOME_ENV_KEY", raising=False)
    with pytest.raises(EnvironmentError):
        qa_rag_system.require_env("SOME_ENV_KEY")


def test_qakg_constraints_with_provider(monkeypatch):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run(self, *_args, **_kwargs):
            return [{"id": "c1", "description": "d", "type": "t", "pattern": "p"}]

    class _Provider:
        def session(self):
            return _Session()

        async def close(self):
            return None

    monkeypatch.setattr(
        qa_rag_system, "AppConfig", lambda *args, **kwargs: types.SimpleNamespace()
    )
    monkeypatch.setattr(
        qa_rag_system,
        "GraphDatabase",
        types.SimpleNamespace(
            driver=lambda *a, **k: types.SimpleNamespace(
                session=lambda: types.SimpleNamespace(close=lambda: None),
                close=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(
        qa_rag_system, "os", types.SimpleNamespace(getenv=lambda *a, **k: None)
    )
    kg = qa_rag_system.QAKnowledgeGraph(graph_provider=_Provider())
    cons = kg.get_constraints_for_query_type("qt")
    assert cons and cons[0]["id"] == "c1"
    kg.close()


@pytest.mark.asyncio
async def test_qakg_constraints_from_async_context(monkeypatch):
    """Test that get_constraints_for_query_type works when called from async context.

    This tests the fix for the "This event loop is already running" error
    when the method is called from within an async function (e.g., interactive_menu).
    """

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def run(self, *_args, **_kwargs):
            return [{"id": "c1", "description": "d", "type": "t", "pattern": "p"}]

    class _Provider:
        def session(self):
            return _Session()

        async def close(self):
            return None

    monkeypatch.setattr(
        qa_rag_system, "AppConfig", lambda *args, **kwargs: types.SimpleNamespace()
    )
    monkeypatch.setattr(
        qa_rag_system,
        "GraphDatabase",
        types.SimpleNamespace(
            driver=lambda *a, **k: types.SimpleNamespace(
                session=lambda: types.SimpleNamespace(close=lambda: None),
                close=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(
        qa_rag_system, "os", types.SimpleNamespace(getenv=lambda *a, **k: None)
    )
    kg = qa_rag_system.QAKnowledgeGraph(graph_provider=_Provider())
    # This should NOT raise "This event loop is already running"
    cons = kg.get_constraints_for_query_type("qt")
    assert cons and cons[0]["id"] == "c1"
    kg.close()


def test_qakg_graph_session_when_loop_running(monkeypatch):
    class _Provider:
        def session(self):
            class _Ctx:
                async def __aenter__(self):
                    return object()

                async def __aexit__(self, exc_type, exc, tb):
                    return False

            return _Ctx()

    loop = types.SimpleNamespace(is_running=lambda: True)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)
    monkeypatch.setattr(
        qa_rag_system, "AppConfig", lambda *a, **k: types.SimpleNamespace()
    )
    monkeypatch.setattr(
        qa_rag_system,
        "GraphDatabase",
        types.SimpleNamespace(
            driver=lambda *a, **k: types.SimpleNamespace(
                session=lambda: types.SimpleNamespace(close=lambda: None),
                close=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(
        qa_rag_system, "os", types.SimpleNamespace(getenv=lambda *a, **k: None)
    )
    kg = qa_rag_system.QAKnowledgeGraph(graph_provider=_Provider())
    with kg.graph_session() as session:
        assert session is None


def test_qakg_vector_store_missing_key(monkeypatch):
    monkeypatch.setattr(
        qa_rag_system, "AppConfig", lambda *a, **k: types.SimpleNamespace()
    )
    monkeypatch.setattr(
        qa_rag_system,
        "GraphDatabase",
        types.SimpleNamespace(
            driver=lambda *a, **k: types.SimpleNamespace(
                session=lambda: types.SimpleNamespace(close=lambda: None),
                close=lambda: None,
            )
        ),
    )
    monkeypatch.setattr(
        qa_rag_system, "os", types.SimpleNamespace(getenv=lambda *a, **k: None)
    )
    kg = qa_rag_system.QAKnowledgeGraph(graph_provider=types.SimpleNamespace())
    assert kg.find_relevant_rules("q") == []


def test_qakg_validate_session_errors(monkeypatch):
    res_empty = qa_rag_system.QAKnowledgeGraph(
        graph_provider=types.SimpleNamespace()
    ).validate_session({"turns": []})
    assert res_empty["ok"] is False

    class _BadSessionCtx:
        def __init__(self, **kwargs):
            raise TypeError("boom")

    monkeypatch.setitem(
        sys.modules,
        "scripts.build_session",
        types.SimpleNamespace(SessionContext=_BadSessionCtx),
    )
    res_bad = qa_rag_system.QAKnowledgeGraph(
        graph_provider=types.SimpleNamespace()
    ).validate_session({"turns": [{"type": "t"}], "context": {"a": 1}})
    assert res_bad["ok"] is False


@pytest.mark.asyncio
async def test_worker_setup_and_close_redis(monkeypatch):
    class _Redis:
        def __init__(self, url):
            self.url = url
            self.closed = False

        @classmethod
        def from_url(cls, url):
            return cls(url)

        async def close(self):
            self.closed = True

        async def ping(self):
            return True

    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    monkeypatch.setitem(
        sys.modules,
        "redis.asyncio",
        types.SimpleNamespace(Redis=_Redis),
    )
    monkeypatch.setattr(infra_worker, "redis_client", None, raising=False)
    await infra_worker.setup_redis()
    assert infra_worker.redis_client is not None
    await infra_worker.close_redis()
    assert infra_worker.redis_client.closed is True


@pytest.mark.asyncio
async def test_worker_ensure_redis_ready_failure(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    class _Redis:
        async def ping(self):
            return False

    monkeypatch.setattr(infra_worker, "redis_client", _Redis(), raising=False)
    with pytest.raises(RuntimeError):
        await infra_worker.ensure_redis_ready()


def test_worker_append_jsonl(tmp_path, monkeypatch):
    path = tmp_path / "out.jsonl"
    worker._append_jsonl(path, {"a": 1})
    data = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert data[0]["a"] == 1


@pytest.mark.asyncio
async def test_run_task_with_lats_agent_error(monkeypatch):
    async def _gen_query(text, meta):
        raise RuntimeError("fail")

    monkeypatch.setattr(
        worker,
        "lats_agent",
        types.SimpleNamespace(generate_query=_gen_query),
        raising=False,
    )
    monkeypatch.setattr(worker, "llm_provider", None, raising=False)
    monkeypatch.setattr(worker, "graph_provider", None, raising=False)

    async def _proc(task):
        return {
            "request_id": task.request_id,
            "session_id": task.session_id,
            "image_path": task.image_path,
            "ocr_text": "hello world",
            "llm_output": None,
            "processed_at": "now",
        }

    monkeypatch.setattr(worker, "_process_task", _proc, raising=False)
    task = worker.OCRTask(request_id="t1", image_path="img", session_id="s1")
    result = await worker._run_task_with_lats(task)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_run_task_with_lats_llm_budget(monkeypatch):
    class _LLM:
        def __init__(self):
            self.calls = 0

        async def generate_content_async(self, prompt, **kwargs):
            self.calls += 1
            return types.SimpleNamespace(
                content="0.8",
                usage={"total_tokens": 10, "prompt_tokens": 4, "completion_tokens": 6},
            )

    monkeypatch.setattr(worker, "lats_agent", None, raising=False)
    monkeypatch.setattr(worker, "llm_provider", _LLM(), raising=False)
    monkeypatch.setattr(worker, "graph_provider", None, raising=False)

    async def _proc(task):
        return {
            "request_id": task.request_id,
            "session_id": task.session_id,
            "image_path": task.image_path,
            "ocr_text": "text data",
            "llm_output": None,
            "processed_at": "now",
        }

    monkeypatch.setattr(worker, "_process_task", _proc, raising=False)
    task = worker.OCRTask(request_id="t2", image_path="img", session_id="s2")
    result = await worker._run_task_with_lats(task)
    assert isinstance(result, dict)
