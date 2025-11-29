import pytest
from jinja2 import DictLoader, Environment

from src.agent import GeminiAgent
from src.config import AppConfig
from typing import Any


class TestDependencyInjection:
    """Dependency Injection 테스트"""

    @pytest.fixture
    def config(self) -> Any:
        """테스트용 설정"""
        return AppConfig()

    @pytest.fixture
    def mock_jinja_env(self) -> Any:
        """Mock Jinja Environment - 실제 파일 없이 테스트 가능"""
        templates = {
            "prompt_eval.j2": "Mock eval template",
            "prompt_query_gen.j2": "Mock query template",
            "prompt_rewrite.j2": "Mock rewrite template",
            "query_gen_user.j2": "OCR: {{ ocr_text }}",
            "rewrite_user.j2": "Rewrite: {{ answer }}",
        }
        loader = DictLoader(templates)
        return Environment(loader=loader)

    def test_agent_with_injected_jinja_env(
        self, config: Any, mock_jinja_env: Any
    ) -> None:
        """외부에서 주입한 Jinja Environment를 사용하는지 확인"""
        agent = GeminiAgent(config, jinja_env=mock_jinja_env)

        assert agent.jinja_env is mock_jinja_env
        assert agent.jinja_env.get_template("query_gen_user.j2") is not None

    def test_agent_without_injected_jinja_env(self, config: Any) -> None:
        """jinja_env 없이 초기화하면 자동으로 생성되는지 확인"""
        agent = GeminiAgent(config)

        assert agent.jinja_env is not None
        # 실제 파일 시스템의 템플릿을 로드해야 함
        assert agent.jinja_env.get_template("prompt_eval.j2") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
