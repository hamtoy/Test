# mypy: disable-error-code=attr-defined
"""Gemini API 전역 초기화 모듈.

google-genai SDK는 클라이언트 인스턴스 기반이므로 전역 설정이 불필요하지만,
기존 코드와의 호환성 및 환경변수 검증을 위해 유지합니다.
"""

import os

from dotenv import load_dotenv

load_dotenv()

_configured = False


def configure_genai(api_key: str | None = None) -> bool:
    """Gemini API 설정 (호환성 유지용).

    새로운 google-genai SDK는 Client 생성 시 API 키를 주입받으므로
    여기서는 환경 변수 설정만 확인/업데이트합니다.

    Args:
        api_key: API 키 (없으면 환경변수에서 로드)

    Returns:
        초기화(검증) 성공 여부
    """
    global _configured

    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        return False

    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    _configured = True
    return True


def is_configured() -> bool:
    """Gemini API 초기화 여부 확인."""
    return _configured
