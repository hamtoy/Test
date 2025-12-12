"""Tests for cache_stats router module.

Covers:
- set_dependencies() and _get_config() functions
- _parse_cache_stats() JSONL parsing
- get_cache_stats_summary() API endpoint
- Error handling (404, 500)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.config import AppConfig
from src.web.routers import cache_stats


class TestSetDependencies:
    """Tests for set_dependencies function."""

    def test_set_dependencies_sets_config(self) -> None:
        """Test that set_dependencies sets the module-level config."""
        mock_config = MagicMock(spec=AppConfig)

        # Clear any existing config
        cache_stats._config = None

        cache_stats.set_dependencies(mock_config)

        assert cache_stats._config is mock_config

    def test_set_dependencies_replaces_existing_config(self) -> None:
        """Test that set_dependencies replaces existing config."""
        old_config = MagicMock(spec=AppConfig)
        new_config = MagicMock(spec=AppConfig)

        cache_stats.set_dependencies(old_config)
        cache_stats.set_dependencies(new_config)

        assert cache_stats._config is new_config


class TestGetConfig:
    """Tests for _get_config function."""

    def test_get_config_returns_set_config(self) -> None:
        """Test _get_config returns the set config."""
        mock_config = MagicMock(spec=AppConfig)
        cache_stats._config = mock_config

        result = cache_stats._get_config()

        assert result is mock_config

    def test_get_config_returns_default_when_none(self) -> None:
        """Test _get_config returns default AppConfig when not set."""
        cache_stats._config = None

        result = cache_stats._get_config()

        assert isinstance(result, AppConfig)

    def teardown_method(self) -> None:
        """Clean up after each test."""
        cache_stats._config = None


class TestParseCacheStats:
    """Tests for _parse_cache_stats function."""

    def test_parse_cache_stats_file_not_found(self, tmp_path: Path) -> None:
        """Test FileNotFoundError when file doesn't exist."""
        non_existent = tmp_path / "nonexistent.jsonl"

        with pytest.raises(FileNotFoundError) as exc_info:
            cache_stats._parse_cache_stats(non_existent)

        assert "Cache stats file not found" in str(exc_info.value)

    def test_parse_cache_stats_empty_file(self, tmp_path: Path) -> None:
        """Test parsing empty file."""
        stats_file = tmp_path / "cache_stats.jsonl"
        stats_file.write_text("")

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 0
        assert result["cache_hits"] == 0
        assert result["cache_misses"] == 0
        assert result["hit_rate_percent"] == 0.0

    def test_parse_cache_stats_with_hits_and_misses(self, tmp_path: Path) -> None:
        """Test parsing file with cache hits and misses."""
        stats_file = tmp_path / "cache_stats.jsonl"
        entries = [
            {
                "cache_status": "hit",
                "token_usage": {"input_tokens": 100, "output_tokens": 50},
                "cost_usd": 0.01,
            },
            {
                "cache_status": "hit",
                "token_usage": {"input_tokens": 200, "output_tokens": 100},
                "cost_usd": 0.02,
            },
            {
                "cache_status": "miss",
                "token_usage": {"input_tokens": 150, "output_tokens": 75},
                "cost_usd": 0.015,
            },
        ]
        stats_file.write_text("\n".join(json.dumps(e) for e in entries))

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 3
        assert result["cache_hits"] == 2
        assert result["cache_misses"] == 1
        assert result["hit_rate_percent"] == pytest.approx(66.67, rel=0.01)
        assert result["total_tokens"]["input"] == 450
        assert result["total_tokens"]["output"] == 225
        assert result["total_tokens"]["total"] == 675
        assert result["total_cost_usd"] == pytest.approx(0.045, rel=0.001)

    def test_parse_cache_stats_skips_empty_lines(self, tmp_path: Path) -> None:
        """Test that empty lines are skipped."""
        stats_file = tmp_path / "cache_stats.jsonl"
        content = '{"cache_status": "hit"}\n\n{"cache_status": "miss"}\n  \n'
        stats_file.write_text(content)

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 2

    def test_parse_cache_stats_skips_malformed_json(self, tmp_path: Path) -> None:
        """Test that malformed JSON lines are skipped."""
        stats_file = tmp_path / "cache_stats.jsonl"
        content = '{"cache_status": "hit"}\nnot valid json\n{"cache_status": "miss"}'
        stats_file.write_text(content)

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 2

    def test_parse_cache_stats_handles_missing_fields(self, tmp_path: Path) -> None:
        """Test handling entries with missing fields."""
        stats_file = tmp_path / "cache_stats.jsonl"
        entries = [
            {"cache_status": "hit"},  # Missing token_usage and cost_usd
            {
                "token_usage": {"input_tokens": 100}
            },  # Missing cache_status and output_tokens
            {},  # Empty entry
        ]
        stats_file.write_text("\n".join(json.dumps(e) for e in entries))

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 3
        assert result["cache_hits"] == 1
        assert result["total_tokens"]["input"] == 100
        assert result["total_tokens"]["output"] == 0

    def test_parse_cache_stats_unknown_status(self, tmp_path: Path) -> None:
        """Test entries with unknown cache status."""
        stats_file = tmp_path / "cache_stats.jsonl"
        entries = [
            {"cache_status": "unknown"},
            {"cache_status": "partial"},
        ]
        stats_file.write_text("\n".join(json.dumps(e) for e in entries))

        result = cache_stats._parse_cache_stats(stats_file)

        assert result["total_entries"] == 2
        assert result["cache_hits"] == 0
        assert result["cache_misses"] == 0
        assert result["hit_rate_percent"] == 0.0


class TestGetCacheStatsSummary:
    """Tests for get_cache_stats_summary endpoint."""

    @pytest.mark.asyncio
    async def test_get_cache_stats_summary_success(self, tmp_path: Path) -> None:
        """Test successful cache stats summary retrieval."""
        stats_file = tmp_path / "cache_stats.jsonl"
        entries = [
            {
                "cache_status": "hit",
                "token_usage": {"input_tokens": 100, "output_tokens": 50},
                "cost_usd": 0.01,
            },
        ]
        stats_file.write_text("\n".join(json.dumps(e) for e in entries))

        mock_config = MagicMock(spec=AppConfig)
        mock_config.cache_stats_path = stats_file
        cache_stats._config = mock_config

        result = await cache_stats.get_cache_stats_summary()

        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["cache_hits"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_stats_summary_file_not_found(self, tmp_path: Path) -> None:
        """Test 404 error when stats file not found."""
        mock_config = MagicMock(spec=AppConfig)
        mock_config.cache_stats_path = tmp_path / "nonexistent.jsonl"
        cache_stats._config = mock_config

        with pytest.raises(HTTPException) as exc_info:
            await cache_stats.get_cache_stats_summary()

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_cache_stats_summary_parse_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test 500 error when parsing fails."""
        stats_file = tmp_path / "cache_stats.jsonl"
        stats_file.write_text('{"valid": "json"}')

        mock_config = MagicMock(spec=AppConfig)
        mock_config.cache_stats_path = stats_file
        cache_stats._config = mock_config

        def raise_error(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Unexpected parsing error")

        monkeypatch.setattr(cache_stats, "_parse_cache_stats", raise_error)

        with pytest.raises(HTTPException) as exc_info:
            await cache_stats.get_cache_stats_summary()

        assert exc_info.value.status_code == 500
        assert "Failed to parse cache statistics" in exc_info.value.detail

    def teardown_method(self) -> None:
        """Clean up after each test."""
        cache_stats._config = None


class TestModuleExports:
    """Tests for module exports."""

    def test_all_exports(self) -> None:
        """Test that __all__ contains expected exports."""
        assert "router" in cache_stats.__all__
        assert "set_dependencies" in cache_stats.__all__
