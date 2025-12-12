"""Extra tests for streaming batch QA generation."""

from __future__ import annotations

import types

import pytest
from fastapi import HTTPException

from src.web.models import GenerateQARequest
from src.web.routers import qa as qa_router


@pytest.mark.asyncio
async def test_stream_batch_rejects_invalid_mode() -> None:
    body = GenerateQARequest(mode="single", qtype="reasoning", ocr_text="OCR")
    with pytest.raises(HTTPException) as excinfo:
        await qa_router.stream_batch_qa_generation(body)
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_stream_batch_requires_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    body = GenerateQARequest(
        mode="batch", batch_types=["global_explanation"], ocr_text="OCR"
    )
    monkeypatch.setattr(qa_router, "_get_agent", lambda: None)
    with pytest.raises(HTTPException) as excinfo:
        await qa_router.stream_batch_qa_generation(body)
    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_stream_batch_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    body = GenerateQARequest(
        mode="batch",
        batch_types=["global_explanation", "target_short"],
        ocr_text="OCR",
    )

    monkeypatch.setattr(qa_router, "_get_agent", lambda: object())
    monkeypatch.setattr(
        qa_router,
        "_get_config",
        lambda: types.SimpleNamespace(qa_single_timeout=5),
    )

    async def _fake_generate(  # noqa: ANN001
        _agent,
        _ocr,
        qtype: str,
        previous_queries=None,
        explanation_answer=None,
    ):
        return {"type": qtype, "query": f"q-{qtype}", "answer": f"a-{qtype}"}

    monkeypatch.setattr(qa_router, "generate_single_qa_with_retry", _fake_generate)

    response = await qa_router.stream_batch_qa_generation(body)
    chunks: list[str] = []
    async for chunk in response.body_iterator:
        if isinstance(chunk, (bytes, bytearray)):
            chunks.append(chunk.decode())
        else:
            chunks.append(str(chunk))

    joined = "".join(chunks)
    assert '"event": "started"' in joined
    assert '"event": "done"' in joined
    assert "q-global_explanation" in joined
