import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, PropertyMock, patch
from src.agent import GeminiAgent
from src.config import AppConfig
from src.core.models import EvaluationResultSchema


class TestGeminiAgent:
    """기본 Agent 기능 테스트"""

    @pytest.fixture
    def config(self):
        """테스트용 설정"""
        return AppConfig()

    @pytest.fixture
    def agent(self, config):
        """테스트용 Agent 인스턴스"""
        return GeminiAgent(config)

    def test_agent_initialization(self, agent):
        """Agent가 올바르게 초기화되는지 확인"""
        assert agent is not None
        assert agent.total_input_tokens == 0
        assert agent.total_output_tokens == 0
        assert agent.jinja_env is not None

    def test_cost_calculation_zero(self, agent):
        """초기 비용이 0인지 확인"""
        cost = agent.get_total_cost()
        assert cost == 0.0

    def test_cost_calculation_with_tokens(self, agent):
        """토큰 사용 시 비용 계산 확인"""
        agent.total_input_tokens = 1_000_000  # 1M tokens
        agent.total_output_tokens = 1_000_000  # 1M tokens

        cost = agent.get_total_cost()
        # gemini-3-pro-preview 기본 단가 적용: 입력 $4.00 + 출력 $18.00 = $22.00
        assert cost == 22.0

    @pytest.mark.asyncio
    async def test_cache_monitoring(self, agent):
        # Mock internal methods to avoid API calls
        agent._create_generative_model = MagicMock()
        agent._call_api_with_retry = AsyncMock(
            return_value='{"best_candidate": "A", "evaluations": []}'
        )

        # Mock lazy properties using patch.object
        mock_genai = MagicMock()
        mock_caching = MagicMock()

        with (
            patch.object(
                GeminiAgent, "_genai", new_callable=PropertyMock
            ) as mock_genai_prop,
            patch.object(
                GeminiAgent, "_caching", new_callable=PropertyMock
            ) as mock_caching_prop,
        ):
            mock_genai_prop.return_value = mock_genai
            mock_caching_prop.return_value = mock_caching

            # Test with cache
            await agent.evaluate_responses(
                "ocr", "query", {"A": "a"}, cached_content=MagicMock()
            )
            assert agent.cache_hits == 1
            assert agent.cache_misses == 0

            # Test without cache
            await agent.evaluate_responses(
                "ocr", "query", {"A": "a"}, cached_content=None
            )
            assert agent.cache_hits == 1
            assert agent.cache_misses == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_concurrency_respected(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("GEMINI_MAX_CONCURRENCY", "1")
        monkeypatch.setenv("LOCAL_CACHE_DIR", str(tmp_path / ".cache"))

        jinja_env = MagicMock()
        jinja_env.get_template.return_value.render.return_value = "prompt"
        agent = GeminiAgent(AppConfig(), jinja_env=jinja_env)
        agent._rate_limiter = None  # use semaphore only

        active = False
        overlap = False

        async def fake_execute(model, prompt_text):
            nonlocal active, overlap
            if active:
                overlap = True
            active = True
            await asyncio.sleep(0.02)
            active = False
            return "ok"

        agent._execute_api_call = fake_execute  # type: ignore

        model = object()
        await asyncio.gather(
            agent._call_api_with_retry(model, "a"),
            agent._call_api_with_retry(model, "b"),
        )

        assert overlap is False

    @pytest.mark.asyncio
    async def test_generate_query_with_cache(self, agent):
        """Verify cached_content is passed to _create_generative_model in generate_query."""
        # Mock internal methods to avoid API calls
        agent._create_generative_model = MagicMock()
        agent._call_api_with_retry = AsyncMock(
            return_value='{"queries": ["query1", "query2"]}'
        )

        # Mock lazy properties using patch.object
        mock_genai = MagicMock()
        mock_caching = MagicMock()
        mock_cache = MagicMock()

        with (
            patch.object(
                GeminiAgent, "_genai", new_callable=PropertyMock
            ) as mock_genai_prop,
            patch.object(
                GeminiAgent, "_caching", new_callable=PropertyMock
            ) as mock_caching_prop,
        ):
            mock_genai_prop.return_value = mock_genai
            mock_caching_prop.return_value = mock_caching

            # Test with cache
            queries = await agent.generate_query(
                "OCR text...",
                cached_content=mock_cache,
            )

            # Verify cached_content is passed to _create_generative_model
            agent._create_generative_model.assert_called_once()
            call_kwargs = agent._create_generative_model.call_args
            assert call_kwargs[1]["cached_content"] == mock_cache

            # Verify cache hit is tracked
            assert agent.cache_hits == 1
            assert agent.cache_misses == 0

            # Verify queries returned correctly
            assert queries == ["query1", "query2"]

    @pytest.mark.asyncio
    async def test_generate_query_without_cache(self, agent):
        """Verify generate_query works without cached_content."""
        # Mock internal methods to avoid API calls
        agent._create_generative_model = MagicMock()
        agent._call_api_with_retry = AsyncMock(
            return_value='{"queries": ["query1"]}'
        )

        # Mock lazy properties using patch.object
        mock_genai = MagicMock()
        mock_caching = MagicMock()

        with (
            patch.object(
                GeminiAgent, "_genai", new_callable=PropertyMock
            ) as mock_genai_prop,
            patch.object(
                GeminiAgent, "_caching", new_callable=PropertyMock
            ) as mock_caching_prop,
        ):
            mock_genai_prop.return_value = mock_genai
            mock_caching_prop.return_value = mock_caching

            # Test without cache
            await agent.generate_query("OCR text...")

            # Verify cached_content is None in _create_generative_model
            agent._create_generative_model.assert_called_once()
            call_kwargs = agent._create_generative_model.call_args
            assert call_kwargs[1]["cached_content"] is None

            # Verify cache miss is tracked
            assert agent.cache_hits == 0
            assert agent.cache_misses == 1

    def test_budget_usage_and_enforcement(self, agent):
        agent.total_input_tokens = 500_000
        agent.total_output_tokens = 250_000
        agent._cost_tracker.config.budget_limit_usd = 0.1

        usage = agent.get_budget_usage_percent()
        assert usage > 0

        agent._cost_tracker.config.budget_limit_usd = 0.00001
        with pytest.raises(Exception):
            agent.check_budget()


class TestEvaluationModel:
    """평가 모델 검증 테스트"""

    def test_model_validation_corrects_hallucination(self):
        """LLM 환각을 자동 수정하는지 확인"""
        # LLM이 A를 최고라고 했지만, 실제로는 B가 더 높은 점수
        data = {
            "best_candidate": "A",
            "evaluations": [
                {"candidate_id": "A", "score": 70, "reason": "Good"},
                {"candidate_id": "B", "score": 90, "reason": "Excellent"},
                {"candidate_id": "C", "score": 60, "reason": "Fair"},
            ],
        }

        result = EvaluationResultSchema(**data)

        # 검증 후 자동으로 B로 수정되어야 함
        assert result.best_candidate == "B"
        assert result.get_best_candidate_id() == "B"

    def test_model_validation_when_correct(self):
        """올바른 경우 변경하지 않는지 확인"""
        data = {
            "best_candidate": "A",
            "evaluations": [
                {"candidate_id": "A", "score": 95, "reason": "Excellent"},
                {"candidate_id": "B", "score": 80, "reason": "Good"},
                {"candidate_id": "C", "score": 70, "reason": "Fair"},
            ],
        }

        result = EvaluationResultSchema(**data)

        # 올바르므로 그대로 유지
        assert result.best_candidate == "A"


# pytest 실행 시 asyncio 이벤트 루프 자동 설정
@pytest.fixture(scope="session")
def event_loop():
    """세션 전체에 동일한 이벤트 루프 사용"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # 직접 실행 시 pytest 실행
    pytest.main([__file__, "-v"])
