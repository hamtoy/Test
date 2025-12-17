# mypy: disable-error-code=attr-defined
"""Gemini API 전역 초기화 모듈."""

import os

from dotenv import load_dotenv

load_dotenv()

_configured = False


def configure_genai(api_key: str | None = None) -> bool:
    """Gemini API 설정 (호환성 유지용).

    Args:
        api_key: API 키 (없으면 환경변수에서 로드)

    Returns:
        초기화(검증) 성공 여부
    """
    global _configured

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return False

    if _configured:
        return True

    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    import google.generativeai as genai

    genai.configure(api_key=key)

    _configured = True
    return True


def is_configured() -> bool:
    """Gemini API 초기화 여부 확인."""
    return _configured
