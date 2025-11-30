"""캐시 TTL 차등 정책

캐시 키 패턴에 따라 최적화된 TTL을 적용합니다.
"""

from __future__ import annotations

from enum import IntEnum


class CacheTTL(IntEnum):
    """캐시 타입별 TTL (초 단위)"""

    SYSTEM_PROMPT = 3600  # 60분 - 거의 변하지 않음
    EVALUATION_PROMPT = 1800  # 30분 - 중간 빈도
    GENERATION_PROMPT = 900  # 15분 - 빈번한 변경
    TEMPORARY = 300  # 5분 - 임시 데이터
    RULES = 3600  # 60분 - 규칙 데이터
    DEFAULT = 600  # 10분 - 기본값


class CacheTTLPolicy:
    """캐시 TTL 정책 관리"""

    # 키 접두사와 TTL 매핑
    _PREFIX_MAP: dict[str, CacheTTL] = {
        "system:": CacheTTL.SYSTEM_PROMPT,
        "eval:": CacheTTL.EVALUATION_PROMPT,
        "gen:": CacheTTL.GENERATION_PROMPT,
        "temp:": CacheTTL.TEMPORARY,
        "rules:": CacheTTL.RULES,
    }

    @classmethod
    def get_ttl(cls, cache_key: str) -> int:
        """캐시 키 패턴에 따라 적절한 TTL 반환

        Args:
            cache_key: 캐시 키 (예: "system:prompt:v1")

        Returns:
            TTL 초 단위
        """
        for prefix, ttl in cls._PREFIX_MAP.items():
            if cache_key.startswith(prefix):
                return int(ttl)
        return int(CacheTTL.DEFAULT)

    @classmethod
    def register_prefix(cls, prefix: str, ttl: CacheTTL) -> None:
        """새로운 접두사-TTL 매핑 등록

        Args:
            prefix: 캐시 키 접두사
            ttl: 적용할 TTL
        """
        cls._PREFIX_MAP[prefix] = ttl

    @classmethod
    def get_all_policies(cls) -> dict[str, int]:
        """모든 TTL 정책 반환

        Returns:
            접두사와 TTL 초 단위 딕셔너리
        """
        return {prefix: int(ttl) for prefix, ttl in cls._PREFIX_MAP.items()}


def calculate_ttl_by_token_count(token_count: int) -> int:
    """토큰 수에 따른 동적 TTL 계산

    토큰 수가 많을수록 캐시 가치가 높으므로 TTL을 늘립니다.

    Args:
        token_count: 캐싱할 컨텐츠의 토큰 수

    Returns:
        TTL 초 단위

    Examples:
        >>> calculate_ttl_by_token_count(3000)
        300
        >>> calculate_ttl_by_token_count(7000)
        600
        >>> calculate_ttl_by_token_count(15000)
        1800
    """
    if token_count < 5000:
        return 5 * 60  # 5분
    elif token_count < 10000:
        return 10 * 60  # 10분
    else:
        return 30 * 60  # 30분


__all__ = ["CacheTTL", "CacheTTLPolicy", "calculate_ttl_by_token_count"]
