"""Extra tests for worker provider initialization."""

from __future__ import annotations

import types

import pytest

from src.infra import worker


def test_init_providers_runs_once_and_skips_second_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_initialized = worker._providers_initialized
    original_graph_provider = worker.graph_provider
    worker._providers_initialized = False
    worker.graph_provider = None

    fake_config = types.SimpleNamespace(
        llm_provider_enabled=False,
        enable_data2neo=False,
    )
    monkeypatch.setattr(worker, "get_config", lambda: fake_config)
    monkeypatch.setattr(worker, "get_graph_provider", lambda _cfg: object())

    worker._init_providers()
    assert worker._providers_initialized is True
    first_graph = worker.graph_provider

    worker._init_providers()
    assert worker.graph_provider is first_graph

    worker._providers_initialized = original_initialized
    worker.graph_provider = original_graph_provider
