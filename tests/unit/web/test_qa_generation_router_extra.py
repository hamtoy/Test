"""Extra tests for qa_generation router."""

from __future__ import annotations

import types

import pytest
from fastapi import HTTPException

from src.web.models import GenerateQARequest
from src.web.routers import qa_generation as qg


@pytest.mark.asyncio
async def test_api_generate_qa_raises_if_agent_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = GenerateQARequest(mode="batch", ocr_text="OCR")
    monkeypatch.setattr(qg, "_get_agent", lambda: None)
    with pytest.raises(HTTPException) as excinfo:
        await qg.api_generate_qa(body)
    assert excinfo.value.status_code == 500


@pytest.mark.asyncio
async def test_api_generate_batch_empty_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = GenerateQARequest(mode="batch", ocr_text="OCR", batch_types=[])
    monkeypatch.setattr(qg, "_get_agent", lambda: object())
    monkeypatch.setattr(
        qg,
        "_get_config",
        lambda: types.SimpleNamespace(qa_single_timeout=1, qa_batch_timeout=2),
    )
    monkeypatch.setattr(qg, "load_ocr_text", lambda _cfg: "OCR")
    with pytest.raises(HTTPException) as excinfo:
        await qg.api_generate_qa(body)
    assert excinfo.value.status_code == 400


@pytest.mark.asyncio
async def test_api_generate_batch_with_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = GenerateQARequest(
        mode="batch",
        ocr_text="OCR",
        batch_types=["global_explanation", "reasoning"],
    )
    monkeypatch.setattr(qg, "_get_agent", lambda: object())
    monkeypatch.setattr(
        qg,
        "_get_config",
        lambda: types.SimpleNamespace(qa_single_timeout=1, qa_batch_timeout=2),
    )
    monkeypatch.setattr(qg, "load_ocr_text", lambda _cfg: "OCR")

    async def _fake_retry(  # noqa: ANN001
        _agent,
        _ocr_text,
        qtype: str,
        previous_queries=None,
        explanation_answer=None,
    ):
        if qtype == "reasoning":
            raise RuntimeError("boom")
        return {"type": qtype, "query": f"q-{qtype}", "answer": "a"}

    def _fake_build_response(data, metadata=None, config=None):  # noqa: ANN001
        return data

    monkeypatch.setattr(qg, "generate_single_qa_with_retry", _fake_retry)
    monkeypatch.setattr(qg, "build_response", _fake_build_response)

    result = await qg.api_generate_qa(body)
    assert result["mode"] == "batch"
    assert result["pairs"][0]["query"].startswith("q-")
    assert any(p["query"] == qg._GENERATION_FAILED_QUERY for p in result["pairs"])


@pytest.mark.asyncio
async def test_api_generate_single_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = GenerateQARequest(mode="single", qtype="reasoning", ocr_text="OCR")
    monkeypatch.setattr(qg, "_get_agent", lambda: object())
    monkeypatch.setattr(
        qg,
        "_get_config",
        lambda: types.SimpleNamespace(qa_single_timeout=1, qa_batch_timeout=2),
    )
    monkeypatch.setattr(qg, "load_ocr_text", lambda _cfg: "OCR")

    async def _fake_single(_agent, _ocr, qtype):  # noqa: ANN001
        return {"type": qtype, "query": "q", "answer": "a"}

    def _fake_build_response(data, metadata=None, config=None):  # noqa: ANN001
        return data

    monkeypatch.setattr(qg, "generate_single_qa", _fake_single)
    monkeypatch.setattr(qg, "build_response", _fake_build_response)

    result = await qg.api_generate_qa(body)
    assert result["mode"] == "single"
    assert result["pair"]["type"] == "reasoning"


@pytest.mark.asyncio
async def test_get_cache_stats_and_clear_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        qg.answer_cache,
        "get_stats",
        lambda: {"hits": 2, "misses": 0, "hit_rate_percent": 100.0, "cache_size": 1},
    )
    stats = await qg.get_cache_stats()
    assert stats["success"] is True
    assert stats["data"]["estimated_time_saved_seconds"] > 0

    async def _fake_clear():  # noqa: ANN001
        return None

    monkeypatch.setattr(qg.answer_cache, "clear", _fake_clear)
    cleared = await qg.clear_cache()
    assert cleared["success"] is True
