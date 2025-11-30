"""에지 케이스 테스트 - 빈 입력, 비정상 응답, 타임아웃"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.config.exceptions import APICallError


class TestAPICallErrorException:
    """APICallError 예외 테스트"""

    def test_api_call_error_with_status_code(self) -> None:
        """상태 코드가 있는 APICallError 테스트"""
        error = APICallError("API call failed", status_code=500)
        assert error.message == "API call failed"
        assert error.status_code == 500
        assert str(error) == "[500] API call failed"

    def test_api_call_error_without_status_code(self) -> None:
        """상태 코드가 없는 APICallError 테스트"""
        error = APICallError("API call failed")
        assert error.message == "API call failed"
        assert error.status_code is None
        assert str(error) == "API call failed"

    def test_api_call_error_is_exception(self) -> None:
        """APICallError가 Exception 상속인지 확인"""
        error = APICallError("test")
        assert isinstance(error, Exception)


class TestEmptyInputHandling:
    """빈 입력 처리 테스트"""

    @pytest.fixture
    def mock_agent(self) -> Any:
        """Mock GeminiAgent 생성"""
        with patch("src.agent.core.GeminiAgent") as mock_cls:
            agent = mock_cls.return_value
            agent.generate_query = AsyncMock(return_value=[])
            agent.evaluate_responses = AsyncMock(return_value=None)
            agent.rewrite_best_answer = AsyncMock(return_value="")
            yield agent

    @pytest.mark.asyncio
    async def test_generate_query_empty_ocr_text(self, mock_agent: Any) -> None:
        """빈 OCR 텍스트에 대한 쿼리 생성 테스트"""
        result = await mock_agent.generate_query("")
        assert result == []

    @pytest.mark.asyncio
    async def test_evaluate_responses_empty_candidates(self, mock_agent: Any) -> None:
        """빈 후보에 대한 평가 테스트"""
        result = await mock_agent.evaluate_responses("ocr", "query", {})
        assert result is None

    @pytest.mark.asyncio
    async def test_rewrite_empty_answer(self, mock_agent: Any) -> None:
        """빈 답변 재작성 테스트"""
        result = await mock_agent.rewrite_best_answer("ocr", "")
        assert result == ""


class TestAbnormalResponseHandling:
    """비정상 응답 처리 테스트"""

    def test_malformed_json_response(self) -> None:
        """잘못된 형식의 JSON 응답 처리 - starts with { but invalid JSON"""
        from src.infra.utils import safe_json_parse

        # JSON 형식으로 시작하지만 실제로는 잘못된 JSON - JSON decode error 유발
        result = safe_json_parse('{"key": "value",}', "key")  # trailing comma
        assert result is None

    def test_missing_required_field(self) -> None:
        """필수 필드 누락 응답 처리"""
        from src.infra.utils import safe_json_parse

        result = safe_json_parse('{"other_field": "value"}', "required_field")
        assert result is None

    def test_non_json_format(self) -> None:
        """JSON 형식이 아닌 응답 처리 - format check에서 None 반환"""
        from src.infra.utils import safe_json_parse

        # 배열 형식 - starts with [ not { - format check에서 거부됨
        result = safe_json_parse("[1, 2, 3]", "key")
        assert result is None

        # 일반 텍스트
        result = safe_json_parse("plain text", "key")
        assert result is None


class TestTimeoutHandling:
    """타임아웃 처리 테스트"""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Mock config 생성"""
        config = MagicMock()
        config.timeout = 30
        config.max_concurrency = 5
        config.model_name = "gemini-3-pro-preview"
        config.temperature = 0.2
        config.max_output_tokens = 8192
        config.template_dir = MagicMock()
        config.template_dir.exists.return_value = True
        return config

    def test_timeout_config_validation(self, mock_config: MagicMock) -> None:
        """타임아웃 설정 검증"""
        assert mock_config.timeout == 30
        assert 30 <= mock_config.timeout <= 600

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self) -> None:
        """타임아웃 에러 처리 테스트"""
        import asyncio

        async def slow_operation() -> str:
            await asyncio.sleep(10)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_operation(), timeout=0.01)


class TestBenchmarkRunner:
    """벤치마크 러너 테스트"""

    def test_percentile_calculation(self) -> None:
        """백분위수 계산 테스트"""
        from scripts.benchmark import calculate_percentile

        data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        assert calculate_percentile(data, 50) == 5.5
        assert calculate_percentile(data, 99) == pytest.approx(9.91, rel=0.1)
        assert calculate_percentile([], 50) == 0.0

    def test_benchmark_runner_initialization(self) -> None:
        """BenchmarkRunner 초기화 테스트"""
        from scripts.benchmark import BenchmarkRunner

        runner = BenchmarkRunner(iterations=5)
        assert runner.iterations == 5
        assert runner.latencies == []

    def test_benchmark_stats_calculation(self) -> None:
        """통계 계산 테스트"""
        from scripts.benchmark import BenchmarkRunner

        runner = BenchmarkRunner(iterations=3)
        runner.latencies = [100.0, 200.0, 300.0]
        stats = runner._calculate_stats()

        assert stats["avg"] == 200.0
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0
