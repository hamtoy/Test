"""캐시 TTL 정책 테스트"""

from src.caching.ttl_policy import (
    CacheTTL,
    CacheTTLPolicy,
    calculate_ttl_by_token_count,
)


class TestCacheTTL:
    """CacheTTL enum 테스트"""

    def test_ttl_values(self) -> None:
        """TTL 값이 올바르게 설정되어 있는지 확인"""
        assert int(CacheTTL.SYSTEM_PROMPT) == 3600
        assert int(CacheTTL.EVALUATION_PROMPT) == 1800
        assert int(CacheTTL.GENERATION_PROMPT) == 900
        assert int(CacheTTL.TEMPORARY) == 300
        assert int(CacheTTL.RULES) == 3600
        assert int(CacheTTL.DEFAULT) == 600

    def test_ttl_is_int(self) -> None:
        """TTL 값이 정수로 변환 가능한지 확인"""
        for ttl in CacheTTL:
            assert isinstance(int(ttl), int)


class TestCacheTTLPolicy:
    """CacheTTLPolicy 클래스 테스트"""

    def test_get_ttl_system_prefix(self) -> None:
        """system: 접두사 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("system:prompt:v1") == 3600
        assert CacheTTLPolicy.get_ttl("system:config") == 3600

    def test_get_ttl_eval_prefix(self) -> None:
        """eval: 접두사 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("eval:compare:abc") == 1800
        assert CacheTTLPolicy.get_ttl("eval:score") == 1800

    def test_get_ttl_gen_prefix(self) -> None:
        """gen: 접두사 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("gen:query:123") == 900
        assert CacheTTLPolicy.get_ttl("gen:response") == 900

    def test_get_ttl_temp_prefix(self) -> None:
        """temp: 접두사 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("temp:session:xyz") == 300
        assert CacheTTLPolicy.get_ttl("temp:data") == 300

    def test_get_ttl_rules_prefix(self) -> None:
        """rules: 접두사 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("rules:explanation") == 3600
        assert CacheTTLPolicy.get_ttl("rules:validation") == 3600

    def test_get_ttl_default(self) -> None:
        """알 수 없는 접두사에 대한 기본 TTL 확인"""
        assert CacheTTLPolicy.get_ttl("unknown:key") == 600
        assert CacheTTLPolicy.get_ttl("other") == 600
        assert CacheTTLPolicy.get_ttl("") == 600

    def test_get_all_policies(self) -> None:
        """모든 정책 반환 확인"""
        policies = CacheTTLPolicy.get_all_policies()
        assert isinstance(policies, dict)
        assert "system:" in policies
        assert "eval:" in policies
        assert "gen:" in policies
        assert "temp:" in policies
        assert "rules:" in policies
        # 모든 값이 정수인지 확인
        for ttl in policies.values():
            assert isinstance(ttl, int)

    def test_register_prefix(self) -> None:
        """새 접두사 등록 테스트"""
        # 새 접두사 등록
        CacheTTLPolicy.register_prefix("custom:", CacheTTL.TEMPORARY)
        assert CacheTTLPolicy.get_ttl("custom:test") == 300

        # 기존 접두사 덮어쓰기 테스트
        original_ttl = CacheTTLPolicy.get_ttl("temp:test")
        CacheTTLPolicy.register_prefix("temp:", CacheTTL.SYSTEM_PROMPT)
        assert CacheTTLPolicy.get_ttl("temp:test") == 3600

        # 원래대로 복원
        CacheTTLPolicy.register_prefix("temp:", CacheTTL.TEMPORARY)
        assert CacheTTLPolicy.get_ttl("temp:test") == original_ttl


class TestCalculateTTLByTokenCount:
    """토큰 수 기반 동적 TTL 계산 테스트"""

    def test_small_token_count(self) -> None:
        """작은 토큰 수 (< 5000)에 대해 5분 TTL 반환"""
        assert calculate_ttl_by_token_count(0) == 300
        assert calculate_ttl_by_token_count(1000) == 300
        assert calculate_ttl_by_token_count(3000) == 300
        assert calculate_ttl_by_token_count(4999) == 300

    def test_medium_token_count(self) -> None:
        """중간 토큰 수 (5000-10000)에 대해 10분 TTL 반환"""
        assert calculate_ttl_by_token_count(5000) == 600
        assert calculate_ttl_by_token_count(7000) == 600
        assert calculate_ttl_by_token_count(9999) == 600

    def test_large_token_count(self) -> None:
        """큰 토큰 수 (>= 10000)에 대해 30분 TTL 반환"""
        assert calculate_ttl_by_token_count(10000) == 1800
        assert calculate_ttl_by_token_count(15000) == 1800
        assert calculate_ttl_by_token_count(100000) == 1800

    def test_boundary_values(self) -> None:
        """경계값 테스트"""
        # 4999 < 5000 이므로 5분
        assert calculate_ttl_by_token_count(4999) == 300
        # 5000 >= 5000 이므로 10분
        assert calculate_ttl_by_token_count(5000) == 600
        # 9999 < 10000 이므로 10분
        assert calculate_ttl_by_token_count(9999) == 600
        # 10000 >= 10000 이므로 30분
        assert calculate_ttl_by_token_count(10000) == 1800
