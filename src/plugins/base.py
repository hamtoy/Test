"""플러그인 기본 인터페이스

모든 플러그인이 구현해야 하는 추상 기본 클래스를 정의합니다.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Plugin(ABC):
    """플러그인 기본 인터페이스

    모든 플러그인은 이 클래스를 상속받아야 합니다.

    Attributes:
        name: 플러그인 이름
        version: 플러그인 버전
        description: 플러그인 설명
    """

    name: str = "unnamed_plugin"
    version: str = "0.1.0"
    description: str = ""

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """플러그인 초기화

        Args:
            config: 플러그인 설정 딕셔너리
        """

    @abstractmethod
    def process(self, context: dict[str, Any]) -> dict[str, Any]:
        """메인 처리 로직

        Args:
            context: 처리할 컨텍스트 데이터

        Returns:
            처리 결과
        """

    def cleanup(self) -> None:
        """정리 작업 (선택적)

        플러그인 종료 시 리소스 정리를 수행합니다.
        """

    def __repr__(self) -> str:
        """Return string representation of the plugin."""
        return f"<Plugin {self.name} v{self.version}>"


__all__ = ["Plugin"]
