"""Extra tests for qa_tools router endpoints."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from src.web.routers import qa_tools


@pytest.mark.asyncio
async def test_validate_qa_pair_returns_error_when_kg_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.web.routers.qa_common.get_cached_kg", lambda: None)
    result = await qa_tools.validate_qa_pair("q", "a", "explanation")
    assert result["success"] is False
    assert "Knowledge graph not available" in result["error"]


@pytest.mark.asyncio
async def test_validate_qa_pair_success_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeCV:
        def __init__(self, _kg: Any) -> None:
            pass

        def cross_validate_qa_pair(self, **_kwargs: Any) -> dict[str, list[str]]:
            return {"consistency_issues": ["x"], "rule_issues": []}

    monkeypatch.setitem(
        sys.modules,
        "src.analysis.cross_validation",
        types.SimpleNamespace(CrossValidationSystem=_FakeCV),
    )
    monkeypatch.setattr("src.web.routers.qa_common.get_cached_kg", lambda: object())

    result = await qa_tools.validate_qa_pair("q", "a", "explanation")
    assert result["success"] is True
    assert result["data"]["consistency_issues"]


@pytest.mark.asyncio
async def test_route_query_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeRouter:
        def __init__(self, kg: Any) -> None:
            self.kg = kg

        def route_and_generate(
            self,
            user_input: str,
            handlers: dict[str, Any],
        ) -> dict[str, str]:
            return {"choice": "summary"}

    monkeypatch.setitem(
        sys.modules,
        "src.routing.graph_router",
        types.SimpleNamespace(GraphEnhancedRouter=_FakeRouter),
    )
    monkeypatch.setattr("src.web.routers.qa_common.get_cached_kg", lambda: object())

    result = await qa_tools.route_query("hello")
    assert result["success"] is True
    assert result["data"]["chosen_type"] == "summary"


@pytest.mark.asyncio
async def test_suggest_next_query_type_handles_invalid_json() -> None:
    result = await qa_tools.suggest_next_query_type(session="{bad")
    assert result["success"] is False
    assert result["error"] == "Invalid session JSON"


@pytest.mark.asyncio
async def test_suggest_next_query_type_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeAutocomplete:
        def __init__(self, _kg: Any) -> None:
            pass

        def suggest_next_query_type(self, session_list: list[str]) -> list[str]:
            return ["reasoning"]

    monkeypatch.setitem(
        sys.modules,
        "src.features.autocomplete",
        types.SimpleNamespace(SmartAutocomplete=_FakeAutocomplete),
    )
    monkeypatch.setattr("src.web.routers.qa_common.get_cached_kg", lambda: object())

    result = await qa_tools.suggest_next_query_type(session="[]")
    assert result["success"] is True
    assert result["data"]["suggestions"] == ["reasoning"]
