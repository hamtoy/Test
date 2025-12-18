"""google-genai SDK 클라이언트 래퍼.

새로운 google-genai SDK를 사용하여 Gemini API를 호출합니다.
기존 google-generativeai SDK에서 마이그레이션하기 위한 래퍼입니다.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, AsyncIterator

from google import genai
from google.genai import types
from pydantic import BaseModel

if TYPE_CHECKING:
    from src.config import AppConfig


class GenAIClient:
    """google-genai SDK 클라이언트 래퍼."""

    def __init__(self, config: AppConfig | None = None):
        """클라이언트 초기화.

        Args:
            config: 앱 설정. None이면 환경 변수에서 API 키를 가져옴.
        """
        api_key = config.api_key if config else os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.config = config

    async def generate_content(
        self,
        *,
        model: str,
        contents: str | list[Any],
        system_instruction: str | None = None,
        temperature: float = 1.0,
        max_output_tokens: int = 4096,
        response_schema: type[BaseModel] | None = None,
        thinking_config: types.ThinkingConfig | None = None,
        safety_settings: list[types.SafetySetting] | None = None,
        cached_content: str | None = None,
    ) -> types.GenerateContentResponse:
        """콘텐츠 생성.

        Args:
            model: 모델 이름
            contents: 프롬프트 내용
            system_instruction: 시스템 지시사항
            temperature: 생성 온도
            max_output_tokens: 최대 출력 토큰
            response_schema: JSON 응답 스키마 (Pydantic 모델)
            thinking_config: Gemini 3 thinking 설정
            safety_settings: 안전 설정
            cached_content: 캐시 콘텐츠 이름

        Returns:
            생성된 콘텐츠 응답
        """
        config_dict: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

        if system_instruction:
            config_dict["system_instruction"] = system_instruction

        if response_schema:
            config_dict["response_mime_type"] = "application/json"
            config_dict["response_schema"] = response_schema

        if thinking_config:
            config_dict["thinking_config"] = thinking_config

        if safety_settings:
            config_dict["safety_settings"] = safety_settings

        if cached_content:
            config_dict["cached_content"] = cached_content

        response = await self.client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_dict),
        )
        return response

    async def generate_content_stream(
        self,
        *,
        model: str,
        contents: str | list[Any],
        system_instruction: str | None = None,
        temperature: float = 1.0,
        max_output_tokens: int = 4096,
    ) -> AsyncIterator[types.GenerateContentResponse]:
        """스트리밍 콘텐츠 생성.

        Args:
            model: 모델 이름
            contents: 프롬프트 내용
            system_instruction: 시스템 지시사항
            temperature: 생성 온도
            max_output_tokens: 최대 출력 토큰

        Yields:
            스트리밍 응답 청크
        """
        config_dict: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }

        if system_instruction:
            config_dict["system_instruction"] = system_instruction

        async for chunk in self.client.aio.models.generate_content_stream(  # type: ignore[attr-defined]
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(**config_dict),
        ):
            yield chunk

    def create_thinking_config(
        self,
        thinking_level: str = "MEDIUM",
    ) -> types.ThinkingConfig:
        """Gemini 2.5용 ThinkingConfig 생성.

        Args:
            thinking_level: 생각 레벨 (MINIMAL, LOW, MEDIUM, HIGH)

        Returns:
            ThinkingConfig 객체
        """
        # Try to use enum directly if available
        try:
            level_enum = getattr(types.ThinkingLevel, thinking_level.upper(), None)
            if level_enum is None:
                level_enum = types.ThinkingLevel.THINKING_LEVEL_UNSPECIFIED
        except AttributeError:
            level_enum = types.ThinkingLevel.THINKING_LEVEL_UNSPECIFIED

        return types.ThinkingConfig(thinking_level=level_enum)

    def create_safety_settings(self) -> list[types.SafetySetting]:
        """기본 안전 설정 생성.

        Returns:
            안전 설정 리스트
        """
        return [
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="BLOCK_NONE",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_NONE",
            ),
        ]


# 싱글톤 인스턴스
_client: GenAIClient | None = None


def get_genai_client(config: AppConfig | None = None) -> GenAIClient:
    """GenAI 클라이언트 싱글톤 인스턴스 가져오기.

    Args:
        config: 앱 설정

    Returns:
        GenAIClient 인스턴스
    """
    global _client
    if _client is None:
        _client = GenAIClient(config)
    return _client
