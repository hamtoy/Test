import pytest
import asyncio
from pathlib import Path
from src.agent import GeminiAgent
from src.config import AppConfig
from src.models import EvaluationResultSchema, QueryResult


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
        # 입력 $3.50 + 출력 $10.50 = $14.00
        assert cost == 14.0


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
                {"candidate_id": "C", "score": 60, "reason": "Fair"}
            ]
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
                {"candidate_id": "C", "score": 70, "reason": "Fair"}
            ]
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
