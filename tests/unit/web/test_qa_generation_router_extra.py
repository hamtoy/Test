"""Extra tests for qa_generation router."""

from __future__ import annotations

import types
from typing import Any

import pytest
from fastapi import HTTPException

from src.web.cache import answer_cache
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

    async def _fake_retry(
        _agent: Any,
        _ocr_text: str,
        qtype: str,
        previous_queries: list[str] | None = None,
        explanation_answer: str | None = None,
    ) -> dict[str, str]:
        if qtype == "reasoning":
            raise RuntimeError("boom")
        return {"type": qtype, "query": f"q-{qtype}", "answer": "a"}

    def _fake_build_response(
        data: Any,
        metadata: Any = None,  # noqa: ARG001
        config: Any = None,  # noqa: ARG001
    ) -> Any:
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

    async def _fake_single(
        _agent: Any,
        _ocr: str,
        qtype: str,
    ) -> dict[str, str]:
        return {"type": qtype, "query": "q", "answer": "a"}

    def _fake_build_response(
        data: Any,
        metadata: Any = None,  # noqa: ARG001
        config: Any = None,  # noqa: ARG001
    ) -> Any:
        return data

    monkeypatch.setattr(qg, "generate_single_qa", _fake_single)
    monkeypatch.setattr(qg, "build_response", _fake_build_response)

    result = await qg.api_generate_qa(body)
    assert result["mode"] == "single"
    assert result["pair"]["type"] == "reasoning"


@pytest.mark.asyncio
async def test_get_cache_stats_and_clear_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        answer_cache,
        "get_stats",
        lambda: {"hits": 2, "misses": 0, "hit_rate_percent": 100.0, "cache_size": 1},
    )
    stats = await qg.get_cache_stats()
    assert stats["success"] is True
    assert stats["data"]["estimated_time_saved_seconds"] > 0

    async def _fake_clear() -> None:
        return None

    monkeypatch.setattr(answer_cache, "clear", _fake_clear)
    cleared = await qg.clear_cache()
    assert cleared["success"] is True
