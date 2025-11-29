"""Tests for src/infra/health.py to improve coverage."""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestCheckRedis:
    """Tests for check_redis function."""

    @pytest.mark.asyncio
    async def test_redis_url_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when REDIS_URL is not set."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        from src.infra.health import check_redis

        result = await check_redis()
        assert result["status"] == "skipped"
        assert "not configured" in result["reason"]

    @pytest.mark.asyncio
    async def test_redis_connection_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful Redis connection."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock()
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            from src.infra.health import check_redis

            result = await check_redis()
            assert result["status"] == "up"
            assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_redis_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when redis.asyncio.from_url raises ImportError."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        # Test the exception handling branch by mocking redis.asyncio.from_url
        # to raise ImportError, simulating the case when redis is not installed
        with patch(
            "redis.asyncio.from_url", side_effect=ImportError("redis not installed")
        ):
            from src.infra.health import check_redis

            result = await check_redis()
            # Should return skipped/down status due to import error
            assert result["status"] in ["skipped", "down"]

    @pytest.mark.asyncio
    async def test_redis_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Redis connection failure."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        mock_client = AsyncMock()
        mock_client.ping = AsyncMock(side_effect=Exception("Connection refused"))

        with patch("redis.asyncio.from_url", return_value=mock_client):
            from src.infra.health import check_redis

            result = await check_redis()
            assert result["status"] == "down"
            assert "error" in result


class TestCheckNeo4j:
    """Tests for check_neo4j function."""

    @pytest.mark.asyncio
    async def test_neo4j_url_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when NEO4J_URI is not set."""
        monkeypatch.delenv("NEO4J_URI", raising=False)
        from src.infra.health import check_neo4j

        result = await check_neo4j()
        assert result["status"] == "skipped"
        assert "not configured" in result["reason"]

    @pytest.mark.asyncio
    async def test_neo4j_connection_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test successful Neo4j connection."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
        monkeypatch.setenv("NEO4J_USER", "neo4j")
        monkeypatch.setenv("NEO4J_PASSWORD", "password")

        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.single.return_value = {"1": 1}
        mock_session.run.return_value = mock_result
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        mock_driver.close = MagicMock()

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            from src.infra.health import check_neo4j

            result = await check_neo4j()
            assert result["status"] == "up"
            assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_neo4j_connection_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test Neo4j connection failure."""
        monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")

        with patch(
            "neo4j.GraphDatabase.driver", side_effect=Exception("Connection failed")
        ):
            from src.infra.health import check_neo4j

            result = await check_neo4j()
            assert result["status"] == "down"
            assert "error" in result


class TestCheckGeminiApi:
    """Tests for check_gemini_api function."""

    @pytest.mark.asyncio
    async def test_gemini_api_key_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when GEMINI_API_KEY is not set."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from src.infra.health import check_gemini_api

        result = await check_gemini_api()
        assert result["status"] == "down"
        assert "not configured" in result["error"]

    @pytest.mark.asyncio
    async def test_gemini_api_key_invalid_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when GEMINI_API_KEY has invalid prefix."""
        monkeypatch.setenv("GEMINI_API_KEY", "INVALID" + "A" * 32)
        from src.infra.health import check_gemini_api

        result = await check_gemini_api()
        assert result["status"] == "down"
        assert "Invalid API key format" in result["error"]

    @pytest.mark.asyncio
    async def test_gemini_api_key_invalid_length(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when GEMINI_API_KEY has invalid length."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza" + "A" * 10)
        from src.infra.health import check_gemini_api

        result = await check_gemini_api()
        assert result["status"] == "down"
        assert "Invalid API key length" in result["error"]

    @pytest.mark.asyncio
    async def test_gemini_api_key_valid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test with valid GEMINI_API_KEY."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        from src.infra.health import check_gemini_api

        result = await check_gemini_api()
        assert result["status"] == "up"
        assert "key_prefix" in result
        assert result["key_prefix"].startswith("AIza")


class TestCheckDisk:
    """Tests for check_disk function."""

    @pytest.mark.asyncio
    async def test_check_disk_success(self) -> None:
        """Test successful disk check."""
        with patch("shutil.disk_usage") as mock_usage:
            # 50% usage
            mock_usage.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)
            from src.infra.health import check_disk

            result = await check_disk()
            assert result["status"] == "up"
            assert "usage_percent" in result
            assert "free_gb" in result

    @pytest.mark.asyncio
    async def test_check_disk_warning(self) -> None:
        """Test disk check with warning level usage."""
        with patch("shutil.disk_usage") as mock_usage:
            # 92% usage (warning threshold is 90%)
            mock_usage.return_value = (100 * 1024**3, 92 * 1024**3, 8 * 1024**3)
            from src.infra.health import check_disk

            result = await check_disk()
            assert result["status"] == "warning"

    @pytest.mark.asyncio
    async def test_check_disk_critical(self) -> None:
        """Test disk check with critical level usage."""
        with patch("shutil.disk_usage") as mock_usage:
            # 96% usage (critical threshold is 95%)
            mock_usage.return_value = (100 * 1024**3, 96 * 1024**3, 4 * 1024**3)
            from src.infra.health import check_disk

            result = await check_disk()
            assert result["status"] == "critical"

    @pytest.mark.asyncio
    async def test_check_disk_error(self) -> None:
        """Test disk check with error."""
        with patch("shutil.disk_usage", side_effect=OSError("Disk error")):
            from src.infra.health import check_disk

            result = await check_disk()
            assert result["status"] == "unknown"
            assert "error" in result


class TestCheckMemory:
    """Tests for check_memory function."""

    @pytest.mark.asyncio
    async def test_check_memory_with_psutil(self) -> None:
        """Test memory check using psutil."""
        mock_memory = MagicMock()
        mock_memory.percent = 50.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from src.infra.health import check_memory

            result = await check_memory()
            assert result["status"] == "up"
            assert "usage_percent" in result

    @pytest.mark.asyncio
    async def test_check_memory_warning(self) -> None:
        """Test memory check with warning level."""
        mock_memory = MagicMock()
        mock_memory.percent = 92.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from src.infra.health import check_memory

            result = await check_memory()
            assert result["status"] == "warning"

    @pytest.mark.asyncio
    async def test_check_memory_critical(self) -> None:
        """Test memory check with critical level."""
        mock_memory = MagicMock()
        mock_memory.percent = 96.0

        with patch("psutil.virtual_memory", return_value=mock_memory):
            from src.infra.health import check_memory

            result = await check_memory()
            assert result["status"] == "critical"


class TestHealthCheckAsync:
    """Tests for health_check_async function."""

    @pytest.mark.asyncio
    async def test_health_check_async_healthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test async health check when all systems are healthy."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)

            mock_memory = MagicMock()
            mock_memory.percent = 50.0

            with patch("psutil.virtual_memory", return_value=mock_memory):
                from src.infra.health import health_check_async

                result = await health_check_async()
                assert result["status"] == "healthy"
                assert "checks" in result
                assert "version" in result
                assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_health_check_async_unhealthy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test async health check when a system is down."""
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = (100 * 1024**3, 50 * 1024**3, 50 * 1024**3)

            mock_memory = MagicMock()
            mock_memory.percent = 50.0

            with patch("psutil.virtual_memory", return_value=mock_memory):
                from src.infra.health import health_check_async

                result = await health_check_async()
                assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_check_async_degraded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test async health check when system is degraded."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        with patch("shutil.disk_usage") as mock_disk:
            # Warning level disk usage
            mock_disk.return_value = (100 * 1024**3, 92 * 1024**3, 8 * 1024**3)

            mock_memory = MagicMock()
            mock_memory.percent = 50.0

            with patch("psutil.virtual_memory", return_value=mock_memory):
                from src.infra.health import health_check_async

                result = await health_check_async()
                assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_health_check_async_exception_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test async health check handles exceptions in checks."""
        valid_key = "AIza" + "A" * 35
        monkeypatch.setenv("GEMINI_API_KEY", valid_key)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        # Make disk check raise an exception
        with patch("shutil.disk_usage", side_effect=Exception("Disk error")):
            mock_memory = MagicMock()
            mock_memory.percent = 50.0

            with patch("psutil.virtual_memory", return_value=mock_memory):
                from src.infra.health import health_check_async

                result = await health_check_async()
                # Should still return a result
                assert "status" in result
                assert "checks" in result


class TestLivenessCheck:
    """Tests for liveness_check function."""

    @pytest.mark.asyncio
    async def test_liveness_check(self) -> None:
        """Test liveness probe returns ok."""
        from src.infra.health import liveness_check

        result = await liveness_check()
        assert result["status"] == "ok"


class TestReadinessCheck:
    """Tests for readiness_check function."""

    @pytest.mark.asyncio
    async def test_readiness_check_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test readiness check when services are ready."""
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)

        from src.infra.health import readiness_check

        result = await readiness_check()
        assert result["ready"] is True
        assert "checks" in result

    @pytest.mark.asyncio
    async def test_readiness_check_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test readiness check when a service is down."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.delenv("NEO4J_URI", raising=False)

        # Mock Redis to fail
        with patch(
            "redis.asyncio.from_url",
            side_effect=Exception("Connection refused"),
        ):
            from src.infra.health import readiness_check

            result = await readiness_check()
            assert result["ready"] is False

    @pytest.mark.asyncio
    async def test_readiness_check_handles_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test readiness check handles exceptions gracefully."""
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.delenv("NEO4J_URI", raising=False)

        async def raise_exception() -> None:
            raise RuntimeError("Unexpected error")

        with patch("src.infra.health.check_redis", side_effect=raise_exception):
            from src.infra.health import readiness_check

            result = await readiness_check()
            assert "checks" in result
