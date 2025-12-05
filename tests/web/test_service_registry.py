"""ServiceRegistry 테스트."""
# mypy: ignore-errors

import pytest
from unittest.mock import Mock

from src.config import AppConfig
from src.web.service_registry import (
    get_registry,
    reset_registry_for_test,
)


def test_service_registry_singleton():
    """싱글톤 패턴 확인."""
    r1 = get_registry()
    r2 = get_registry()
    assert r1 is r2


def test_service_registry_register_config():
    """Config 등록 테스트."""
    reset_registry_for_test()
    registry = get_registry()

    config = AppConfig()
    registry.register_config(config)

    assert registry.config == config


def test_service_registry_uninitialized_error():
    """초기화 전 접근 시 에러."""
    reset_registry_for_test()
    registry = get_registry()

    with pytest.raises(RuntimeError, match="Config not registered"):
        _ = registry.config


def test_service_registry_is_initialized():
    """초기화 상태 확인."""
    reset_registry_for_test()
    registry = get_registry()

    assert not registry.is_initialized()

    # Config만 등록
    registry.register_config(AppConfig())
    assert not registry.is_initialized()  # Agent도 필요

    # Agent 등록 (mock)
    registry.register_agent(Mock())
    assert registry.is_initialized()


def test_service_registry_clear():
    """Clear 테스트."""
    reset_registry_for_test()
    registry = get_registry()

    registry.register_config(AppConfig())
    assert registry._config is not None

    registry.clear()
    assert registry._config is None


def test_service_registry_register_agent():
    """Agent 등록 테스트."""
    reset_registry_for_test()
    registry = get_registry()

    # Agent 없이 접근 시 에러
    with pytest.raises(RuntimeError, match="Agent not registered"):
        _ = registry.agent

    # Agent 등록
    mock_agent = Mock()
    registry.register_agent(mock_agent)
    assert registry.agent == mock_agent


def test_service_registry_register_kg():
    """KG 등록 테스트."""
    reset_registry_for_test()
    registry = get_registry()

    mock_kg = Mock()
    registry.register_kg(mock_kg)

    assert registry.kg == mock_kg

    # None도 등록 가능
    registry.register_kg(None)
    assert registry.kg is None


def test_service_registry_register_pipeline():
    """Pipeline 등록 테스트."""
    reset_registry_for_test()
    registry = get_registry()

    mock_pipeline = Mock()
    registry.register_pipeline(mock_pipeline)

    assert registry.pipeline == mock_pipeline

    # None도 등록 가능
    registry.register_pipeline(None)
    assert registry.pipeline is None
