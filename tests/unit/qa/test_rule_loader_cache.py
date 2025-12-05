"""RuleLoader 전역 캐싱 테스트."""

from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, Mock

import pytest

from src.qa.rule_loader import (
    RuleLoader,
    clear_global_rule_cache,
    get_global_cache_info,
    set_global_kg,
)


@pytest.fixture(autouse=True)
def reset_global_cache() -> Generator[None, None, None]:
    """각 테스트 전후 전역 캐시 초기화."""
    clear_global_rule_cache()
    set_global_kg(None)
    yield
    clear_global_rule_cache()
    set_global_kg(None)


def test_global_cache_hit() -> None:
    """동일 질의 타입은 전역 캐시를 재사용한다."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(
        return_value=[{"text": "규칙 1"}, {"text": "규칙 2"}]
    )
    set_global_kg(mock_kg)

    loader = RuleLoader(mock_kg)

    rules1 = loader.get_rules_for_type("explanation", [])
    assert len(rules1) == 2
    assert mock_kg.get_rules_for_query_type.call_count == 1

    rules2 = loader.get_rules_for_type("explanation", [])
    assert len(rules2) == 2
    assert mock_kg.get_rules_for_query_type.call_count == 1  # 캐시 히트
    assert rules1 == rules2


def test_global_cache_shared_across_instances() -> None:
    """RuleLoader 인스턴스끼리 캐시를 공유한다."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(return_value=[{"text": "공유 규칙"}])
    set_global_kg(mock_kg)

    loader1 = RuleLoader(mock_kg)
    loader1.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1

    loader2 = RuleLoader(mock_kg)
    loader2.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1  # 캐시 히트


def test_cache_info() -> None:
    """캐시 통계를 확인할 수 있다."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(return_value=[{"text": "규칙 1"}])
    set_global_kg(mock_kg)

    loader = RuleLoader(mock_kg)

    info = get_global_cache_info()
    assert info["hits"] == 0
    assert info["misses"] == 0

    loader.get_rules_for_type("explanation", [])
    info = get_global_cache_info()
    assert info["misses"] == 1

    loader.get_rules_for_type("explanation", [])
    info = get_global_cache_info()
    assert info["hits"] == 1
    assert info["hit_rate"] == 0.5


def test_clear_global_cache() -> None:
    """캐시 초기화 후 다시 쿼리 호출된다."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(return_value=[{"text": "규칙 1"}])
    set_global_kg(mock_kg)

    loader = RuleLoader(mock_kg)

    loader.get_rules_for_type("explanation", [])
    loader.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 1

    clear_global_rule_cache()

    loader.get_rules_for_type("explanation", [])
    assert mock_kg.get_rules_for_query_type.call_count == 2


def test_no_global_kg_set_returns_defaults() -> None:
    """전역 KG가 없으면 기본값을 반환한다."""
    loader = RuleLoader(None)
    defaults = ["기본 규칙 1", "기본 규칙 2"]
    rules = loader.get_rules_for_type("explanation", defaults)
    assert rules == defaults


def test_kg_exception_returns_defaults() -> None:
    """KG 호출 예외 시 기본값을 반환한다."""
    mock_kg = Mock()
    mock_kg.get_rules_for_query_type = MagicMock(side_effect=Exception("Neo4j error"))
    set_global_kg(mock_kg)

    loader = RuleLoader(mock_kg)
    defaults = ["기본 규칙 1"]
    rules = loader.get_rules_for_type("explanation", defaults)
    assert rules == defaults
