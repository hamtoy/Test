"""Mock Neo4j driver for testing."""

from typing import Any, Generator

import pytest


class MockNeo4jRecord:
    """Mock Neo4j record."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize with data dictionary."""
        self._data = data

    def data(self) -> dict[str, Any]:
        """Return record data."""
        return self._data

    def __getitem__(self, key: str) -> Any:
        """Get item by key."""
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get item by key with default."""
        return self._data.get(key, default)


class MockNeo4jResult:
    """Mock Neo4j query result."""

    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        """Initialize with optional records."""
        self._records = [MockNeo4jRecord(r) for r in (records or [])]
        self._index = 0

    def data(self) -> list[dict[str, Any]]:
        """Return all records as list of dicts."""
        return [r.data() for r in self._records]

    def single(self) -> MockNeo4jRecord | None:
        """Return single record or None."""
        return self._records[0] if self._records else None

    def __iter__(self) -> "MockNeo4jResult":
        """Return iterator."""
        self._index = 0
        return self

    def __next__(self) -> MockNeo4jRecord:
        """Return next record."""
        if self._index < len(self._records):
            record = self._records[self._index]
            self._index += 1
            return record
        raise StopIteration


class MockNeo4jSession:
    """Mock Neo4j session."""

    def __init__(self) -> None:
        """Initialize mock session."""
        self._results: list[dict[str, Any]] = []

    def run(
        self, query: str, parameters: dict[str, Any] | None = None
    ) -> MockNeo4jResult:
        """Execute a query and return mock result."""
        return MockNeo4jResult(self._results)

    def set_results(self, results: list[dict[str, Any]]) -> None:
        """Set the results to return from queries."""
        self._results = results

    def close(self) -> None:
        """Close the session."""
        pass

    def __enter__(self) -> "MockNeo4jSession":
        """Enter context manager."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context manager."""
        self.close()


class MockNeo4jDriver:
    """Mock Neo4j driver for testing."""

    def __init__(self) -> None:
        """Initialize mock driver."""
        self._closed = False
        self._session = MockNeo4jSession()

    def session(self, **kwargs: Any) -> MockNeo4jSession:
        """Return a mock session."""
        return self._session

    def close(self) -> None:
        """Close the driver."""
        self._closed = True

    def verify_connectivity(self) -> None:
        """Verify driver connectivity (always succeeds for mock)."""
        pass

    @property
    def closed(self) -> bool:
        """Check if driver is closed."""
        return self._closed


@pytest.fixture
def mock_neo4j_driver() -> Generator[MockNeo4jDriver, None, None]:
    """Provide a mock Neo4j driver for testing.

    Yields:
        MockNeo4jDriver: A mock Neo4j driver instance.
    """
    driver = MockNeo4jDriver()
    yield driver
    driver.close()
