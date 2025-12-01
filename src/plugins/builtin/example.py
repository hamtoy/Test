"""예제 플러그인

플러그인 구현 방법을 보여주는 예제입니다.
"""

from __future__ import annotations

from typing import Any

from src.plugins.base import Plugin


class ExamplePlugin(Plugin):
    """예제 플러그인

    플러그인 구현 방법을 보여줍니다.
    """

    name = "example"
    version = "1.0.0"
    description = "예제 플러그인 - 입력 텍스트를 대문자로 변환"

    def __init__(self) -> None:
        """Initialize the example plugin."""
        self._prefix: str = ""

    def initialize(self, config: dict[str, Any]) -> None:
        """플러그인 초기화

        Args:
            config: prefix를 포함할 수 있는 설정 딕셔너리
        """
        self._prefix = config.get("prefix", "[EXAMPLE]")

    def process(self, context: dict[str, Any]) -> dict[str, Any]:
        """텍스트를 대문자로 변환

        Args:
            context: text 키를 포함한 컨텍스트

        Returns:
            변환된 텍스트가 담긴 딕셔너리
        """
        text = context.get("text", "")
        result = f"{self._prefix} {text.upper()}"
        return {"text": result, "transformed": True}

    def cleanup(self) -> None:
        """정리 작업"""
        self._prefix = ""


__all__ = ["ExamplePlugin"]
