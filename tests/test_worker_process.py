import pytest

pytest.importorskip("faststream")
from src import worker  # noqa: E402


@pytest.mark.asyncio
async def test_process_task_without_llm(tmp_path, monkeypatch):
    txt = tmp_path / "sample.txt"
    txt.write_text("hello world", encoding="utf-8")

    monkeypatch.setattr(worker, "llm_provider", None)

    task = worker.OCRTask(request_id="r1", image_path=str(txt), session_id="s1")
    result = await worker._process_task(task)

    assert result["ocr_text"] == "hello world"
    assert result["llm_output"] is None
    assert result["request_id"] == "r1"


@pytest.mark.asyncio
async def test_process_task_with_llm(monkeypatch):
    class _FakeResult:
        def __init__(self, content: str):
            self.content = content
            self.usage: dict[str, int] = {}

    class _FakeProvider:
        async def generate_content_async(self, **kwargs):  # noqa: ANN001
            return _FakeResult("cleaned")

    monkeypatch.setattr(worker, "llm_provider", _FakeProvider())

    task = worker.OCRTask(
        request_id="r2", image_path="img.png", session_id="s2"
    )  # non-txt path
    result = await worker._process_task(task)

    assert result["llm_output"] == "cleaned"
    assert "OCR placeholder" in result["ocr_text"]


@pytest.mark.asyncio
async def test_ensure_redis_ready(monkeypatch):
    class _Redis:
        async def ping(self):
            return True

    monkeypatch.setattr(worker, "redis_client", _Redis())
    await worker.ensure_redis_ready()


@pytest.mark.asyncio
async def test_check_rate_limit_allows_then_blocks(monkeypatch):
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
    monkeypatch.setattr(worker, "redis_client", mock_redis)

    assert await worker.check_rate_limit("k", limit=2, window=5) is True
    assert await worker.check_rate_limit("k", limit=2, window=5) is True
    assert await worker.check_rate_limit("k", limit=2, window=5) is False
    assert mock_redis.expire_called is True


@pytest.mark.asyncio
async def test_check_rate_limit_fail_open(monkeypatch):
    monkeypatch.setattr(worker, "redis_client", None)
    assert await worker.check_rate_limit("k", limit=1, window=1) is True


@pytest.mark.asyncio
async def test_handle_ocr_task_success(monkeypatch, tmp_path):
    # no-op prechecks
    async def _ready():
        return None

    monkeypatch.setattr(worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(worker, "check_rate_limit", _allow)

    # capture jsonl writes
    written: list[dict] = []

    def _append(_path, record):
        written.append(record)

    monkeypatch.setattr(worker, "_append_jsonl", _append)

    # stub processing
    async def _proc(_task):
        return {"request_id": "r3", "session_id": "s3", "image_path": "img", "ocr_text": "t", "llm_output": None, "processed_at": "now"}  # fmt: skip

    monkeypatch.setattr(worker, "_process_task", _proc)

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(worker, "broker", broker)

    task = worker.OCRTask(request_id="r3", image_path="img", session_id="s3")
    await worker.handle_ocr_task(task)

    assert written and written[0]["request_id"] == "r3"
    assert broker.published == []


@pytest.mark.asyncio
async def test_handle_ocr_task_rate_limited(monkeypatch):
    async def _ready():
        return None

    monkeypatch.setattr(worker, "ensure_redis_ready", _ready)

    async def _deny(*_args, **_kwargs):
        return False

    monkeypatch.setattr(worker, "check_rate_limit", _deny)

    task = worker.OCRTask(request_id="r4", image_path="img", session_id="s4")
    with pytest.raises(worker.RateLimitError):
        await worker.handle_ocr_task(task)


@pytest.mark.asyncio
async def test_handle_ocr_task_sends_dlq(monkeypatch):
    async def _ready():
        return None

    monkeypatch.setattr(worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(worker, "check_rate_limit", _allow)

    async def _proc(_task):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "_process_task", _proc)
    monkeypatch.setattr(worker, "_append_jsonl", lambda *_args, **_kwargs: None)

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(worker, "broker", broker)

    task = worker.OCRTask(request_id="r5", image_path="img", session_id="s5")
    await worker.handle_ocr_task(task)

    assert len(broker.published) == 1
    channel, msg = broker.published[0]
    assert channel == "ocr_dlq"
    assert getattr(msg, "request_id") == "r5"


@pytest.mark.asyncio
async def test_handle_ocr_task_lats_toggle(monkeypatch):
    async def _ready():
        return None

    monkeypatch.setattr(worker, "ensure_redis_ready", _ready)

    async def _allow(*_args, **_kwargs):
        return True

    monkeypatch.setattr(worker, "check_rate_limit", _allow)

    monkeypatch.setattr(worker.config, "enable_lats", True, raising=False)

    written: list[dict] = []
    monkeypatch.setattr(worker, "_append_jsonl", lambda _p, rec: written.append(rec))

    class _Broker:
        def __init__(self):
            self.published: list = []

        async def publish(self, msg, channel):
            self.published.append((channel, msg))

    broker = _Broker()
    monkeypatch.setattr(worker, "broker", broker)

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

    monkeypatch.setattr(worker, "_process_task", _process)

    task = worker.OCRTask(request_id="l1", image_path="img", session_id="s-lats")
    await worker.handle_ocr_task(task)

    assert written and written[0]["request_id"] == "l1"
    assert broker.published == []
