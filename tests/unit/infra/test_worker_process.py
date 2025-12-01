import types
from pathlib import Path
from typing import Any

import pytest

# Note: GEMINI_API_KEY is set in tests/conftest.py before any imports
# to handle AppConfig validation during test collection.

pytest.importorskip("faststream")
from src.infra import worker  # noqa: E402


@pytest.mark.asyncio
async def test_process_task_without_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.infra import worker as infra_worker

    txt = tmp_path / "sample.txt"
    txt.write_text("hello world", encoding="utf-8")
    monkeypatch.setattr(infra_worker, "llm_provider", None)
    task = worker.OCRTask(request_id="r1", image_path=str(txt), session_id="s1")
    result = await infra_worker._process_task(task)
    assert result["ocr_text"] == "hello world"
    assert result["llm_output"] is None
    assert result["request_id"] == "r1"


@pytest.mark.asyncio
async def test_process_task_with_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    class _FakeResult:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage: dict[str, int] = {}

    class _FakeProvider:
        async def generate_content_async(self, **kwargs: Any) -> _FakeResult:
            return _FakeResult("cleaned")

    monkeypatch.setattr(infra_worker, "llm_provider", _FakeProvider())
    task = worker.OCRTask(request_id="r2", image_path="img.png", session_id="s2")
    result = await infra_worker._process_task(task)
    assert result["llm_output"] == "cleaned"
    assert "OCR placeholder" in result["ocr_text"]


@pytest.mark.asyncio
async def test_ensure_redis_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    class _Redis:
        async def ping(self) -> bool:
            return True

    monkeypatch.setattr(infra_worker, "redis_client", _Redis())
    await infra_worker.ensure_redis_ready()


@pytest.mark.asyncio
async def test_check_rate_limit_allows_then_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.infra import worker as infra_worker

    class _Redis:
        def __init__(self) -> None:
            self.count = 0
            self.expire_called = False

        async def incr(self, _key: str) -> int:
            self.count += 1
            return self.count

        async def expire(self, _key: str, _window: int) -> None:
            self.expire_called = True

    mock_redis = _Redis()
    monkeypatch.setattr(infra_worker, "redis_client", mock_redis)
    assert await infra_worker.check_rate_limit("k", limit=2, window=5) is True
    assert await infra_worker.check_rate_limit("k", limit=2, window=5) is True
    assert await infra_worker.check_rate_limit("k", limit=2, window=5) is False
    assert mock_redis.expire_called is True


@pytest.mark.asyncio
async def test_check_rate_limit_fail_open(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    monkeypatch.setattr(infra_worker, "redis_client", None)
    assert await infra_worker.check_rate_limit("k", limit=1, window=1) is True


@pytest.mark.asyncio
async def test_lats_budget_uses_cost_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker
    from src.infra import budget as infra_budget

    class _FakeLLM:
        async def generate_content_async(
            self, prompt: str, **kwargs: Any
        ) -> types.SimpleNamespace:
            return types.SimpleNamespace(
                content="ok",
                usage={"total_tokens": 10, "prompt_tokens": 4, "completion_tokens": 6},
            )

    class _FakeBudgetTracker:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.total_cost_usd = 0.0

        def record_usage(self, usage: dict[str, int]) -> types.SimpleNamespace:
            cost = 0.1
            self.total_cost_usd += cost
            return types.SimpleNamespace(
                cost_usd=cost, total_tokens=usage.get("total_tokens", 0)
            )

        def get_total_cost(self) -> float:
            return self.total_cost_usd

    cost_calls: list[float] = []
    original_update_budget = worker.SearchState.update_budget

    def _spy_update_budget(self: Any, tokens: int = 0, cost: float = 0.0) -> Any:
        cost_calls.append(cost)
        return original_update_budget(self, tokens=tokens, cost=cost)

    # Create a mock config with the required attributes
    mock_config = types.SimpleNamespace(
        max_output_tokens=128,
        budget_limit_usd=1.0,
        enable_lats=False,
        enable_data2neo=False,
        temperature=0.7,
        timeout=30,
    )
    monkeypatch.setattr(infra_worker, "get_config", lambda: mock_config)

    monkeypatch.setattr(worker.SearchState, "update_budget", _spy_update_budget)
    monkeypatch.setattr(infra_budget, "BudgetTracker", _FakeBudgetTracker)
    monkeypatch.setattr(infra_worker, "llm_provider", _FakeLLM(), raising=False)
    monkeypatch.setattr(infra_worker, "graph_provider", None, raising=False)
    monkeypatch.setattr(infra_worker, "lats_agent", None, raising=False)
    monkeypatch.setattr(infra_worker, "redis_client", None, raising=False)
    task = worker.OCRTask(request_id="cost1", image_path="img", session_id="s1")
    await infra_worker._run_task_with_lats(task)
    non_zero_costs = [c for c in cost_calls if c > 0]
    assert len(non_zero_costs) >= 2
    assert all(abs(c - 0.1) < 1e-9 for c in non_zero_costs)


@pytest.mark.asyncio
async def test_handle_ocr_task_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.infra import worker as infra_worker

    async def _ready() -> None:
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)
    written: list[dict[str, Any]] = []

    def _append(_path: str, record: dict[str, Any]) -> None:
        written.append(record)

    monkeypatch.setattr(infra_worker, "_append_jsonl", _append)

    async def _proc(_task: Any) -> dict[str, Any]:
        return {
            "request_id": "r3",
            "session_id": "s3",
            "image_path": "img",
            "ocr_text": "t",
            "llm_output": None,
            "processed_at": "now",
        }

    monkeypatch.setattr(infra_worker, "_process_task", _proc)

    class _Broker:
        def __init__(self) -> None:
            self.published: list[Any] = []

        async def publish(self, msg: Any, channel: str) -> None:
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)
    task = worker.OCRTask(request_id="r3", image_path="img", session_id="s3")
    await infra_worker.handle_ocr_task(task)
    assert written and written[0]["request_id"] == "r3"
    assert broker.published == []


@pytest.mark.asyncio
async def test_handle_ocr_task_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    async def _ready() -> None:
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _deny(*_args: Any, **_kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(infra_worker, "check_rate_limit", _deny)
    task = worker.OCRTask(request_id="r4", image_path="img", session_id="s4")
    with pytest.raises(worker.RateLimitError):
        await infra_worker.handle_ocr_task(task)


@pytest.mark.asyncio
async def test_handle_ocr_task_sends_dlq(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    async def _ready() -> None:
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    async def _proc(_task: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(infra_worker, "_process_task", _proc)
    monkeypatch.setattr(infra_worker, "_append_jsonl", lambda *_args, **_kwargs: None)

    class _Broker:
        def __init__(self) -> None:
            self.published: list[Any] = []

        async def publish(self, msg: Any, channel: str) -> None:
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)
    task = worker.OCRTask(request_id="r5", image_path="img", session_id="s5")
    await infra_worker.handle_ocr_task(task)
    assert len(broker.published) == 1
    channel, msg = broker.published[0]
    assert channel == "ocr_dlq"
    assert getattr(msg, "request_id") == "r5"


@pytest.mark.asyncio
async def test_handle_ocr_task_lats_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infra import worker as infra_worker

    async def _ready() -> None:
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    # Create a mock config with enable_lats=True
    mock_config = types.SimpleNamespace(
        enable_lats=True,
        enable_data2neo=False,
    )
    monkeypatch.setattr(infra_worker, "get_config", lambda: mock_config)

    written: list[dict[str, Any]] = []
    monkeypatch.setattr(
        infra_worker, "_append_jsonl", lambda _p, rec: written.append(rec)
    )

    class _Broker:
        def __init__(self) -> None:
            self.published: list[Any] = []

        async def publish(self, msg: Any, channel: str) -> None:
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)

    async def _process(task: Any) -> dict[str, Any]:
        return {
            "request_id": task.request_id,
            "session_id": task.session_id,
            "image_path": task.image_path,
            "ocr_text": "hello world",
            "llm_output": None,
            "processed_at": "now",
        }

    monkeypatch.setattr(infra_worker, "_process_task", _process)
    task = worker.OCRTask(request_id="l1", image_path="img", session_id="s-lats")
    await infra_worker.handle_ocr_task(task)
    assert written and written[0]["request_id"] == "l1"
    assert broker.published == []


@pytest.mark.asyncio
async def test_handle_ocr_task_lats_budget_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.infra import worker as infra_worker

    async def _ready() -> None:
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    # Create a mock config with enable_lats=True and budget_limit_usd=0.0
    mock_config = types.SimpleNamespace(
        enable_lats=True,
        enable_data2neo=False,
        budget_limit_usd=0.0,
    )
    monkeypatch.setattr(infra_worker, "get_config", lambda: mock_config)

    async def _process(task: Any) -> dict[str, Any]:
        return {
            "request_id": task.request_id,
            "session_id": task.session_id,
            "image_path": task.image_path,
            "ocr_text": "hello world",
            "llm_output": None,
            "processed_at": "now",
        }

    monkeypatch.setattr(infra_worker, "_process_task", _process)
    monkeypatch.setattr(infra_worker, "llm_provider", None, raising=False)
    written: list[dict[str, Any]] = []
    monkeypatch.setattr(
        infra_worker, "_append_jsonl", lambda _p, rec: written.append(rec)
    )

    class _Broker:
        def __init__(self) -> None:
            self.published: list[Any] = []

        async def publish(self, msg: Any, channel: str) -> None:
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)
    task = worker.OCRTask(request_id="l2", image_path="img", session_id="s-budget")
    await infra_worker.handle_ocr_task(task)
    assert written and written[0]["request_id"] == "l2"
    assert broker.published == []
