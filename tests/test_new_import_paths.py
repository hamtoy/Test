"""Test that new import paths work correctly."""



class TestNewImportPaths:
    """Test that new import paths work correctly without warnings."""

    def test_config_imports(self):
        """Test imports from src.config package."""
        from src.config import AppConfig
        from src.config.constants import ERROR_MESSAGES, LOG_MESSAGES
        from src.config.exceptions import (
            APIRateLimitError,
            BudgetExceededError,
            CacheCreationError,
        )

        assert AppConfig is not None
        assert ERROR_MESSAGES is not None
        assert LOG_MESSAGES is not None
        assert BudgetExceededError is not None
        assert APIRateLimitError is not None
        assert CacheCreationError is not None

    def test_core_imports(self):
        """Test imports from src.core package."""
        from src.core.models import (
            EvaluationItem,
            EvaluationResultSchema,
            QueryResult,
            WorkflowResult,
        )

        assert WorkflowResult is not None
        assert EvaluationResultSchema is not None
        assert EvaluationItem is not None
        assert QueryResult is not None

    def test_agent_imports(self):
        """Test imports from src.agent package."""
        from src.agent import GeminiAgent
        from src.agent.cache_manager import CacheManager
        from src.agent.cost_tracker import CostTracker

        assert GeminiAgent is not None
        assert CostTracker is not None
        assert CacheManager is not None

    def test_infra_imports(self):
        """Test imports from src.infra package."""
        from src.infra.logging import log_metrics, setup_logging
        from src.infra.neo4j import SafeDriver, create_sync_driver
        from src.infra.utils import clean_markdown_code_block, safe_json_parse

        assert clean_markdown_code_block is not None
        assert safe_json_parse is not None
        assert setup_logging is not None
        assert log_metrics is not None
        assert SafeDriver is not None
        assert create_sync_driver is not None

    def test_qa_imports(self):
        """Test imports from src.qa package."""
        from src.qa.rag_system import QAKnowledgeGraph

        assert QAKnowledgeGraph is not None

    def test_llm_imports(self):
        """Test imports from src.llm package."""
        from src.llm.gemini import GeminiModelClient

        assert GeminiModelClient is not None

    def test_processing_imports(self):
        """Test imports from src.processing package."""
        from src.processing.loader import (
            load_file_async,
            load_input_data,
            parse_raw_candidates,
        )

        assert load_input_data is not None
        assert load_file_async is not None
        assert parse_raw_candidates is not None

    def test_caching_imports(self):
        """Test imports from src.caching package."""
        from src.caching.layer import CachingLayer

        assert CachingLayer is not None

    def test_routing_imports(self):
        """Test imports from src.routing package."""
        from src.routing.graph_router import GraphEnhancedRouter

        assert GraphEnhancedRouter is not None

    def test_workflow_imports(self):
        """Test imports from src.workflow package."""
        from src.workflow.executor import WorkflowExecutor
        from src.workflow.processor import WorkflowProcessor

        assert WorkflowExecutor is not None
        assert WorkflowProcessor is not None

    def test_features_imports(self):
        """Test imports from src.features package."""
        from src.features.autocomplete import SmartAutocomplete
        from src.features.difficulty import AdaptiveDifficultyAdjuster

        assert SmartAutocomplete is not None
        assert AdaptiveDifficultyAdjuster is not None

    def test_analysis_imports(self):
        """Test imports from src.analysis package."""
        from src.analysis.cross_validation import DocumentComparer

        assert DocumentComparer is not None

    def test_import_equivalence(self):
        """Test that old and new imports refer to the same objects."""
        import warnings

        # Suppress warnings for this test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            # Import from both old and new paths
            from src.constants import ERROR_MESSAGES as old_errors
            from src.config.constants import ERROR_MESSAGES as new_errors

            from src.exceptions import BudgetExceededError as old_budget
            from src.config.exceptions import BudgetExceededError as new_budget

            from src.models import WorkflowResult as old_workflow
            from src.core.models import WorkflowResult as new_workflow

            from src.utils import clean_markdown_code_block as old_clean
            from src.infra.utils import clean_markdown_code_block as new_clean

            # Verify they are the same objects
            assert old_errors is new_errors
            assert old_budget is new_budget
            assert old_workflow is new_workflow
            assert old_clean is new_clean
