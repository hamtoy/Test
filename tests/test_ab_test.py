"""Tests for the A/B testing framework."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.qa.ab_test import ExperimentConfig, ExperimentResult, PromptExperimentManager


class TestExperimentResult:
    """Tests for ExperimentResult dataclass."""

    def test_experiment_result_creation(self):
        result = ExperimentResult(
            variant_name="control",
            input_id="doc_1",
            response="test response",
            latency=0.5,
            token_count=100,
            cost=0.001,
            success=True,
        )
        assert result.variant_name == "control"
        assert result.input_id == "doc_1"
        assert result.success is True
        assert result.error_msg is None

    def test_experiment_result_with_error(self):
        result = ExperimentResult(
            variant_name="treatment",
            input_id="doc_2",
            response="",
            latency=0.1,
            token_count=0,
            cost=0.0,
            success=False,
            error_msg="API error",
        )
        assert result.success is False
        assert result.error_msg == "API error"


class TestExperimentConfig:
    """Tests for ExperimentConfig dataclass."""

    def test_experiment_config_defaults(self):
        config = ExperimentConfig(
            name="test_experiment",
            control_prompt_template="control.j2",
            treatment_prompt_template="treatment.j2",
        )
        assert config.name == "test_experiment"
        assert config.sample_size == 10
        assert config.output_dir == "experiments/results"

    def test_experiment_config_custom_values(self):
        config = ExperimentConfig(
            name="custom_test",
            control_prompt_template="control.j2",
            treatment_prompt_template="treatment.j2",
            sample_size=5,
            output_dir="/tmp/experiments",
        )
        assert config.sample_size == 5
        assert config.output_dir == "/tmp/experiments"


class TestPromptExperimentManager:
    """Tests for PromptExperimentManager class."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock GeminiAgent."""
        agent = MagicMock()
        agent.generate_query = AsyncMock(return_value=["query1", "query2"])
        return agent

    @pytest.fixture
    def manager(self, mock_agent):
        """Create a PromptExperimentManager instance."""
        return PromptExperimentManager(mock_agent)

    @pytest.fixture
    def test_dataset(self):
        """Create test dataset."""
        return [
            {"id": "doc_1", "input_text": "Test document 1"},
            {"id": "doc_2", "input_text": "Test document 2"},
            {"id": "doc_3", "input_text": "Test document 3"},
        ]

    @pytest.mark.asyncio
    async def test_run_batch_success(self, manager, test_dataset):
        """Test running a batch of experiments successfully."""
        results = await manager._run_batch("control", "template.j2", test_dataset)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(r.variant_name == "control" for r in results)

    @pytest.mark.asyncio
    async def test_run_batch_with_error(self, manager, test_dataset):
        """Test handling errors during batch execution."""
        manager.agent.generate_query = AsyncMock(side_effect=Exception("API error"))

        results = await manager._run_batch("treatment", "template.j2", test_dataset)

        assert len(results) == 3
        assert all(not r.success for r in results)
        assert all(r.error_msg == "API error" for r in results)

    @pytest.mark.asyncio
    async def test_run_experiment(self, manager, test_dataset, tmp_path):
        """Test running a complete experiment."""
        config = ExperimentConfig(
            name="test_exp",
            control_prompt_template="control.j2",
            treatment_prompt_template="treatment.j2",
            sample_size=2,
            output_dir=str(tmp_path),
        )

        report = await manager.run_experiment(config, test_dataset)

        assert report["experiment"] == "test_exp"
        assert "control" in report
        assert "treatment" in report
        assert "winner" in report
        assert report["control"]["success_rate"] == 1.0
        assert report["treatment"]["success_rate"] == 1.0

    def test_generate_report(self, manager):
        """Test report generation logic."""
        control_results = [
            ExperimentResult(
                variant_name="control",
                input_id="1",
                response="resp",
                latency=1.0,
                token_count=100,
                cost=0.01,
                success=True,
            ),
            ExperimentResult(
                variant_name="control",
                input_id="2",
                response="resp",
                latency=2.0,
                token_count=100,
                cost=0.02,
                success=True,
            ),
        ]
        treatment_results = [
            ExperimentResult(
                variant_name="treatment",
                input_id="1",
                response="resp",
                latency=0.5,
                token_count=50,
                cost=0.005,
                success=True,
            ),
            ExperimentResult(
                variant_name="treatment",
                input_id="2",
                response="resp",
                latency=0.5,
                token_count=50,
                cost=0.005,
                success=True,
            ),
        ]

        report = manager._generate_report("test", control_results, treatment_results)

        assert report["experiment"] == "test"
        assert report["control"]["avg_latency"] == 1.5
        assert report["treatment"]["avg_latency"] == 0.5
        # Treatment is faster and cheaper
        assert report["winner"] == "Treatment (Faster & Cheaper)"

    def test_generate_report_manual_review(self, manager):
        """Test report when winner is not clear."""
        control_results = [
            ExperimentResult(
                variant_name="control",
                input_id="1",
                response="resp",
                latency=0.5,
                token_count=100,
                cost=0.005,
                success=True,
            ),
        ]
        treatment_results = [
            ExperimentResult(
                variant_name="treatment",
                input_id="1",
                response="resp",
                latency=1.0,
                token_count=50,
                cost=0.002,
                success=True,
            ),
        ]

        report = manager._generate_report("test", control_results, treatment_results)

        # Treatment is cheaper but slower
        assert report["winner"] == "Manual Review Required"

    def test_save_results(self, manager, tmp_path):
        """Test saving experiment results to file."""
        config = ExperimentConfig(
            name="save_test",
            control_prompt_template="control.j2",
            treatment_prompt_template="treatment.j2",
            output_dir=str(tmp_path),
        )
        report = {
            "experiment": "save_test",
            "timestamp": "2025-01-01 00:00:00",
            "control": {"avg_latency": 1.0},
            "treatment": {"avg_latency": 0.5},
            "winner": "Treatment",
        }

        manager._save_results(config, report)

        # Check that file was created
        result_files = list(tmp_path.glob("save_test_*.json"))
        assert len(result_files) == 1

        # Check file contents
        with open(result_files[0]) as f:
            saved_report = json.load(f)
        assert saved_report["experiment"] == "save_test"

    def test_generate_report_empty_results(self, manager):
        """Test report generation with empty results."""
        report = manager._generate_report("empty_test", [], [])

        assert report["control"]["success_rate"] == 0
        assert report["treatment"]["success_rate"] == 0

    @pytest.mark.asyncio
    async def test_run_batch_with_user_intent(self, manager):
        """Test batch execution includes user_intent."""
        samples = [
            {
                "id": "doc_1",
                "input_text": "Test text",
                "user_intent": "Extract info",
            }
        ]

        await manager._run_batch("control", "template.j2", samples)

        # Check that generate_query was called with user_intent
        manager.agent.generate_query.assert_called_once()
        call_kwargs = manager.agent.generate_query.call_args.kwargs
        assert call_kwargs["user_intent"] == "Extract info"
