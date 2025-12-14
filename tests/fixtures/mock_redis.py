"""Mock Redis client for testing."""

from typing import Any, Generator
from unittest.mock import AsyncMock

import pytest


class MockRedisClient:
    """Mock async Redis client for testing.

    Provides an in-memory implementation of common Redis operations.
    """

    def __init__(self) -> None:
        """Initialize mock Redis client with empty data store."""
        self._data: dict[str, Any] = {}
        self._expiry: dict[str, int] = {}

        # Set up async mocks that delegate to internal methods
        self.get = AsyncMock(side_effect=self._get)
        self.set = AsyncMock(side_effect=self._set)
        self.delete = AsyncMock(side_effect=self._delete)
        self.exists = AsyncMock(side_effect=self._exists)
        self.keys = AsyncMock(side_effect=self._keys)
        self.close = AsyncMock()
        self.ping = AsyncMock(return_value=True)

    async def _get(self, key: str) -> Any:
        """Get value by key."""
        return self._data.get(key)

    async def _set(
        self,
        key: str,
        value: Any,
        ex: int | None = None,
        px: int | None = None,
        nx: bool = False,
        xx: bool = False,
        **kwargs: Any,
    ) -> bool:
        """Set a key-value pair with optional expiration."""
        if nx and key in self._data:
            return False
        if xx and key not in self._data:
            return False

        self._data[key] = value
        if ex is not None:
            self._expiry[key] = ex
        return True

    async def _delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                self._expiry.pop(key, None)
                deleted += 1
        return deleted

    async def _exists(self, *keys: str) -> int:
        """Check if keys exist."""
        return sum(1 for key in keys if key in self._data)

    async def _keys(self, pattern: str = "*") -> list[str]:
        """Get keys matching pattern (simplified matching)."""
        if pattern == "*":
            return list(self._data.keys())
        # Simple prefix matching for patterns like "prefix:*"
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._data if k.startswith(prefix)]
        return [k for k in self._data if k == pattern]

    def clear(self) -> None:
        """Clear all data (useful for test cleanup)."""
        self._data.clear()
        self._expiry.clear()

    @property
    def data(self) -> dict[str, Any]:
        """Access internal data store for test assertions."""
        return self._data


@pytest.fixture
def mock_redis_client() -> Generator[MockRedisClient, None, None]:
    """Provide a mock Redis client for testing.

    Yields:
        MockRedisClient: A mock Redis client instance.
    """
    client = MockRedisClient()
    yield client
    client.clear()
