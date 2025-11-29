"""Tests for cache threshold validation and settings.

These tests verify that the 2048 token minimum threshold for Gemini Context Caching
is properly enforced and documented.
"""

import logging

import pytest

from src.agent.cache_manager import CacheManager
from src.config import AppConfig
from src.config.constants import CacheConfig

VALID_API_KEY = "AIza" + "A" * 35


class TestCacheConfigConstants:
    """Test CacheConfig class constants."""

    def test_min_tokens_for_caching_value(self):
        """Verify MIN_TOKENS_FOR_CACHING is 2048."""
        assert CacheConfig.MIN_TOKENS_FOR_CACHING == 2048

    def test_min_tokens_rationale_exists(self):
        """Verify MIN_TOKENS_RATIONALE documentation exists."""
        assert CacheConfig.MIN_TOKENS_RATIONALE
        assert "2048" in CacheConfig.MIN_TOKENS_RATIONALE
        assert "Gemini" in CacheConfig.MIN_TOKENS_RATIONALE


class TestCacheSettingsValidation:
    """Test CacheSettings validator."""

    def test_minimum_cache_tokens_auto_correction(self, monkeypatch, tmp_path):
        """2048 미만 설정 시 자동 조정 확인."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("GEMINI_CACHE_MIN_TOKENS", "1000")

        config = AppConfig()
        # 자동 조정
        assert config.cache_min_tokens == 2048

    def test_exact_min_tokens(self, monkeypatch, tmp_path):
        """정확한 값 설정 확인."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("GEMINI_CACHE_MIN_TOKENS", "2048")

        config = AppConfig()
        assert config.cache_min_tokens == 2048

    def test_higher_min_tokens_allowed(self, monkeypatch, tmp_path):
        """더 큰 값 (허용되지만 경고)."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("GEMINI_CACHE_MIN_TOKENS", "5000")

        config = AppConfig()
        assert config.cache_min_tokens == 5000

    def test_default_min_tokens(self, monkeypatch, tmp_path):
        """기본값 확인."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        config = AppConfig()
        assert config.cache_min_tokens == 2048


class TestCacheManagerThreshold:
    """Test CacheManager threshold logic."""

    @pytest.fixture
    def cache_manager(self, monkeypatch, tmp_path) -> CacheManager:
        """Create a CacheManager with test configuration."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        config = AppConfig()
        return CacheManager(config, min_tokens=2048)

    def test_should_cache_below_threshold(self, cache_manager):
        """경계값 테스트: 2047 토큰."""
        assert cache_manager.should_cache(2047) is False

    def test_should_cache_at_threshold(self, cache_manager):
        """경계값 테스트: 2048 토큰."""
        assert cache_manager.should_cache(2048) is True

    def test_should_cache_above_threshold(self, cache_manager):
        """경계값 테스트: 2049 토큰."""
        assert cache_manager.should_cache(2049) is True

    def test_should_cache_short_prompt(self, cache_manager):
        """실제 사용 케이스: 짧은 프롬프트."""
        assert cache_manager.should_cache(1000) is False

    def test_should_cache_medium_prompt(self, cache_manager):
        """실제 사용 케이스: 중간 프롬프트."""
        assert cache_manager.should_cache(5000) is True

    def test_should_cache_long_prompt(self, cache_manager):
        """실제 사용 케이스: 긴 프롬프트."""
        assert cache_manager.should_cache(50000) is True


class TestSavingsEstimation:
    """Test savings estimation function."""

    @pytest.fixture
    def cache_manager(self, monkeypatch, tmp_path) -> CacheManager:
        """Create a CacheManager with test configuration."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        config = AppConfig()
        return CacheManager(config, min_tokens=2048)

    def test_estimate_savings_small(self, cache_manager):
        """절감률 추정: 작은 프롬프트."""
        assert cache_manager._estimate_savings(3000) == 50

    def test_estimate_savings_medium(self, cache_manager):
        """절감률 추정: 중간 프롬프트."""
        assert cache_manager._estimate_savings(10000) == 70

    def test_estimate_savings_large(self, cache_manager):
        """절감률 추정: 큰 프롬프트."""
        assert cache_manager._estimate_savings(50000) == 85


class TestCacheManagerLogging:
    """Test CacheManager logging behavior."""

    def test_should_cache_logs_skip_message(self, monkeypatch, tmp_path, caplog):
        """캐싱 건너뜀 로그 확인."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        config = AppConfig()
        manager = CacheManager(config, min_tokens=2048)

        with caplog.at_level(logging.DEBUG):
            manager.should_cache(1000)

        assert "캐싱 건너뜀" in caplog.text
        assert "1000" in caplog.text
        assert "2048" in caplog.text

    def test_should_cache_logs_activation_message(self, monkeypatch, tmp_path, caplog):
        """캐싱 활성화 로그 확인."""
        monkeypatch.setenv("GEMINI_API_KEY", VALID_API_KEY)
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))

        config = AppConfig()
        manager = CacheManager(config, min_tokens=2048)

        with caplog.at_level(logging.DEBUG):
            manager.should_cache(5000)

        assert "캐싱 활성화" in caplog.text
        assert "5000" in caplog.text
