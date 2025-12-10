# mypy: disable-error-code=attr-defined
"""Gemini API 전역 초기화 모듈.

genai.configure()는 프로세스당 1회만 호출되어야 합니다.
이 모듈을 import하면 자동으로 초기화됩니다.
"""

import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

_configured = False


def configure_genai(api_key: str | None = None) -> bool:
    """Gemini API를 전역으로 1회 초기화.

    Args:
        api_key: API 키 (없으면 환경변수에서 로드)

    Returns:
        초기화 성공 여부
    """
    global _configured
    if _configured:
        return True

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return False

    genai.configure(api_key=key)
    _configured = True
    return True


def is_configured() -> bool:
    """Gemini API 초기화 여부 확인."""
    return _configured
