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
            self.usage = {}

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

    monkeypatch.setattr(worker.broker, "redis", _Redis())
    await worker.ensure_redis_ready()
