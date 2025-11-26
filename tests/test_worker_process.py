import os
import types

import pytest

# For BudgetTracker monkeypatching in LATS tests
import src.budget_tracker as budget_tracker

# Ensure required env is present for AppConfig during import
os.environ.setdefault("GEMINI_API_KEY", "AIza" + "0" * 35)

pytest.importorskip("faststream")
from src import worker  # noqa: E402


@pytest.mark.asyncio
async def test_process_task_without_llm(tmp_path, monkeypatch):
    # Import the actual worker module to patch the right namespace
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
async def test_process_task_with_llm(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    class _FakeResult:
        def __init__(self, content: str):
            self.content = content
            self.usage: dict[str, int] = {}

    class _FakeProvider:
        async def generate_content_async(self, **kwargs):  # noqa: ANN001
            return _FakeResult("cleaned")

    monkeypatch.setattr(infra_worker, "llm_provider", _FakeProvider())

    task = worker.OCRTask(
        request_id="r2", image_path="img.png", session_id="s2"
    )  # non-txt path
    result = await infra_worker._process_task(task)

    assert result["llm_output"] == "cleaned"
    assert "OCR placeholder" in result["ocr_text"]


@pytest.mark.asyncio
async def test_ensure_redis_ready(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    class _Redis:
        async def ping(self):
            return True

    monkeypatch.setattr(infra_worker, "redis_client", _Redis())
    await infra_worker.ensure_redis_ready()


@pytest.mark.asyncio
async def test_check_rate_limit_allows_then_blocks(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    class _Redis:
        def __init__(self):
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
async def test_check_rate_limit_fail_open(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    monkeypatch.setattr(infra_worker, "redis_client", None)
    assert await infra_worker.check_rate_limit("k", limit=1, window=1) is True


@pytest.mark.asyncio
async def test_lats_budget_uses_cost_delta(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker
    from src.infra import budget as infra_budget

    class _FakeLLM:
        async def generate_content_async(self, prompt, **kwargs):  # noqa: ANN001
            return types.SimpleNamespace(
                content="ok",
                usage={
                    "total_tokens": 10,
                    "prompt_tokens": 4,
                    "completion_tokens": 6,
                },
            )

    class _FakeBudgetTracker:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, D401
            self.total_cost_usd = 0.0

        def record_usage(self, usage):  # noqa: ANN001
            cost = 0.1
            self.total_cost_usd += cost
            return types.SimpleNamespace(
                cost_usd=cost, total_tokens=usage.get("total_tokens", 0)
            )

        def get_total_cost(self):  # noqa: D401
            return self.total_cost_usd

    cost_calls: list[float] = []
    original_update_budget = worker.SearchState.update_budget

    def _spy_update_budget(self, tokens: int = 0, cost: float = 0.0):  # type: ignore[override]
        cost_calls.append(cost)
        return original_update_budget(self, tokens=tokens, cost=cost)

    monkeypatch.setattr(worker.SearchState, "update_budget", _spy_update_budget)
    monkeypatch.setattr(infra_budget, "BudgetTracker", _FakeBudgetTracker)
    monkeypatch.setattr(infra_worker, "llm_provider", _FakeLLM(), raising=False)
    monkeypatch.setattr(infra_worker, "graph_provider", None, raising=False)
    monkeypatch.setattr(infra_worker, "lats_agent", None, raising=False)
    monkeypatch.setattr(infra_worker, "redis_client", None, raising=False)
    monkeypatch.setattr(infra_worker.config, "max_output_tokens", 128, raising=False)

    task = worker.OCRTask(request_id="cost1", image_path="img", session_id="s1")
    await infra_worker._run_task_with_lats(task)

    non_zero_costs = [c for c in cost_calls if c > 0]
    assert len(non_zero_costs) >= 2  # multiple evaluations should occur
    assert all(abs(c - 0.1) < 1e-9 for c in non_zero_costs)


@pytest.mark.asyncio
async def test_handle_ocr_task_success(monkeypatch, tmp_path):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    # no-op prechecks
    async def _ready():
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    # capture jsonl writes
    written: list[dict] = []

    def _append(_path, record):
        written.append(record)

    monkeypatch.setattr(infra_worker, "_append_jsonl", _append)

    # stub processing
    async def _proc(_task):
        return {"request_id": "r3", "session_id": "s3", "image_path": "img", "ocr_text": "t", "llm_output": None, "processed_at": "now"}  # fmt: skip

    monkeypatch.setattr(infra_worker, "_process_task", _proc)

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)

    task = worker.OCRTask(request_id="r3", image_path="img", session_id="s3")
    await infra_worker.handle_ocr_task(task)

    assert written and written[0]["request_id"] == "r3"
    assert broker.published == []


@pytest.mark.asyncio
async def test_handle_ocr_task_rate_limited(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    async def _ready():
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr(infra_worker, "check_rate_limit", _deny)

    task = worker.OCRTask(request_id="r4", image_path="img", session_id="s4")
    with pytest.raises(worker.RateLimitError):
        await infra_worker.handle_ocr_task(task)


@pytest.mark.asyncio
async def test_handle_ocr_task_sends_dlq(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    async def _ready():
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    async def _proc(_task):
        raise RuntimeError("boom")

    monkeypatch.setattr(infra_worker, "_process_task", _proc)
    monkeypatch.setattr(infra_worker, "_append_jsonl", lambda *_args, **_kwargs: None)

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
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
async def test_handle_ocr_task_lats_toggle(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    async def _ready():
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    monkeypatch.setattr(infra_worker.config, "enable_lats", True, raising=False)

    written: list[dict] = []
    monkeypatch.setattr(infra_worker, "_append_jsonl", lambda _p, rec: written.append(rec))

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)

    # use real lats wrapper but ensure deterministic content
    async def _process(task):
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
async def test_handle_ocr_task_lats_budget_exit(monkeypatch):
    # Import the actual worker module to patch the right namespace
    from src.infra import worker as infra_worker

    async def _ready():
        return None

    monkeypatch.setattr(infra_worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(infra_worker, "check_rate_limit", _allow)

    monkeypatch.setattr(infra_worker.config, "enable_lats", True, raising=False)
    monkeypatch.setattr(infra_worker.config, "budget_limit_usd", 0.0, raising=False)

    async def _process(task):
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

    written: list[dict] = []
    monkeypatch.setattr(infra_worker, "_append_jsonl", lambda _p, rec: written.append(rec))

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(infra_worker, "broker", broker)

    task = worker.OCRTask(request_id="l2", image_path="img", session_id="s-budget")
    await infra_worker.handle_ocr_task(task)

    assert written and written[0]["request_id"] == "l2"
    assert broker.published == []
