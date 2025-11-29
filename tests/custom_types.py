"""테스트에서 자주 쓰는 타입 정의.

이 모듈은 테스트 코드의 타입 안정성을 높이기 위한 공통 타입 정의를 제공합니다.

사용 예시:
    from tests.custom_types import MockRedis, ProgressCallbackType

    @pytest.fixture
    def mock_redis() -> MockRedis:
        return cast(MockRedis, MagicMock())

    def test_with_progress(callback: ProgressCallbackType) -> None:
        callback(1, 10)  # current=1, total=10
"""

from typing import Any, Awaitable, Callable, Protocol, TypeVar


# Mock 타입 정의
class MockRedis(Protocol):
    """Redis 클라이언트 Mock 프로토콜."""

    def get(self, key: str) -> str | None:
        """키로 값을 가져옵니다."""
        ...

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        """키에 값을 설정합니다."""
        ...

    def setex(self, key: str, ttl: int, value: str) -> bool:
        """TTL과 함께 키에 값을 설정합니다."""
        ...

    def keys(self, pattern: str) -> list[str]:
        """패턴에 맞는 키 목록을 반환합니다."""
        ...

    def delete(self, *keys: str) -> int:
        """키를 삭제합니다."""
        ...


class MockNeo4j(Protocol):
    """Neo4j 드라이버 Mock 프로토콜."""

    def run(self, query: str, **params: Any) -> list[dict[str, Any]]:
        """Cypher 쿼리를 실행합니다."""
        ...


class MockSession(Protocol):
    """Neo4j 세션 Mock 프로토콜."""

    def __enter__(self) -> "MockSession":
        """Context manager 진입."""
        ...

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any
    ) -> bool:
        """Context manager 종료."""
        ...

    def run(self, cypher: str, **params: Any) -> Any:
        """Cypher 쿼리를 실행합니다."""
        ...


# 제네릭 타입
T = TypeVar("T")
R = TypeVar("R")
ResultType = TypeVar("ResultType")

# Fixture 타입 별칭
# NOTE: Python 3.12+ 에서는 `type ConfigFixture = ...` 문법 사용 가능
# 현재는 호환성을 위해 TypeVar 기반 타입 별칭 사용

# 테스트에서 자주 사용되는 함수 시그니처 타입
ProcessFnType = Callable[[T], Any]
AsyncProcessFnType = Callable[[T], Awaitable[R]]
ProgressCallbackType = Callable[[int, int], None]
