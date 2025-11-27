"""Test that deprecated imports are removed in v3.0.

In v3.0, all shim files have been removed. Importing from the old paths
should raise ModuleNotFoundError instead of emitting deprecation warnings.
"""

import sys
import warnings

import pytest


class TestV3RemovedShims:
    """Test that deprecated shim imports raise ModuleNotFoundError in v3.0."""

    def test_constants_shim_removed(self):
        """Test that importing from src.constants raises ModuleNotFoundError."""
        # Clear module cache
        sys.modules.pop("src.constants", None)

        with pytest.raises(ModuleNotFoundError):
            import src.constants  # type: ignore[import-not-found]  # noqa: F401

    def test_exceptions_shim_removed(self):
        """Test that importing from src.exceptions raises ModuleNotFoundError."""
        sys.modules.pop("src.exceptions", None)

        with pytest.raises(ModuleNotFoundError):
            import src.exceptions  # type: ignore[import-not-found]  # noqa: F401

    def test_models_shim_removed(self):
        """Test that importing from src.models raises ModuleNotFoundError."""
        sys.modules.pop("src.models", None)

        with pytest.raises(ModuleNotFoundError):
            import src.models  # type: ignore[import-not-found]  # noqa: F401

    def test_utils_shim_removed(self):
        """Test that importing from src.utils raises ModuleNotFoundError."""
        sys.modules.pop("src.utils", None)

        with pytest.raises(ModuleNotFoundError):
            import src.utils  # type: ignore[import-not-found]  # noqa: F401

    def test_logging_setup_shim_removed(self):
        """Test that importing from src.logging_setup raises ModuleNotFoundError."""
        sys.modules.pop("src.logging_setup", None)

        with pytest.raises(ModuleNotFoundError):
            import src.logging_setup  # type: ignore[import-not-found]  # noqa: F401

    def test_neo4j_utils_shim_removed(self):
        """Test that importing from src.neo4j_utils raises ModuleNotFoundError."""
        sys.modules.pop("src.neo4j_utils", None)

        with pytest.raises(ModuleNotFoundError):
            import src.neo4j_utils  # type: ignore[import-not-found]  # noqa: F401

    def test_worker_shim_removed(self):
        """Test that importing from src.worker raises ModuleNotFoundError."""
        sys.modules.pop("src.worker", None)

        with pytest.raises(ModuleNotFoundError):
            import src.worker  # type: ignore[import-not-found]  # noqa: F401

    def test_data_loader_shim_removed(self):
        """Test that importing from src.data_loader raises ModuleNotFoundError."""
        sys.modules.pop("src.data_loader", None)

        with pytest.raises(ModuleNotFoundError):
            import src.data_loader  # type: ignore[import-not-found]  # noqa: F401

    def test_qa_rag_system_shim_removed(self):
        """Test that importing qa_rag_system from src raises ImportError."""
        with pytest.raises(ImportError):
            from src import qa_rag_system  # type: ignore[attr-defined]  # noqa: F401

    def test_caching_layer_shim_removed(self):
        """Test that importing from src.caching_layer raises ModuleNotFoundError."""
        sys.modules.pop("src.caching_layer", None)

        with pytest.raises(ModuleNotFoundError):
            import src.caching_layer  # type: ignore[import-not-found]  # noqa: F401

    def test_graph_enhanced_router_shim_removed(self):
        """Test that importing from src.graph_enhanced_router raises ModuleNotFoundError."""
        sys.modules.pop("src.graph_enhanced_router", None)

        with pytest.raises(ModuleNotFoundError):
            import src.graph_enhanced_router  # type: ignore[import-not-found]  # noqa: F401


class TestV3NewImportPaths:
    """Test that the new import paths work correctly in v3.0."""

    def test_config_package_import(self):
        """Test that importing AppConfig from src.config package works without warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # This should work without warning as it's importing from the package
            from src.config import AppConfig  # noqa: F401

            # Filter out any unrelated warnings
            deprecation_warnings = [
                warn for warn in w if issubclass(warn.category, DeprecationWarning)
            ]
            # Should have exactly 0 deprecation warnings since we're using the package import
            assert len(deprecation_warnings) == 0

    def test_constants_from_config_package(self):
        """Test that importing from src.config.constants works."""
        from src.config.constants import ERROR_MESSAGES  # noqa: F401

    def test_exceptions_from_config_package(self):
        """Test that importing from src.config.exceptions works."""
        from src.config.exceptions import BudgetExceededError  # noqa: F401

    def test_models_from_core_package(self):
        """Test that importing from src.core.models works."""
        from src.core.models import WorkflowResult  # noqa: F401

    def test_utils_from_infra_package(self):
        """Test that importing from src.infra.utils works."""
        from src.infra.utils import clean_markdown_code_block  # noqa: F401

    def test_qa_from_qa_package(self):
        """Test that importing from src.qa.rag_system works."""
        from src.qa.rag_system import QAKnowledgeGraph  # noqa: F401

    def test_caching_from_caching_package(self):
        """Test that importing from src.caching.layer works."""
        from src.caching.layer import CachingLayer  # noqa: F401

    def test_routing_from_routing_package(self):
        """Test that importing from src.routing.graph_router works."""
        from src.routing.graph_router import GraphEnhancedRouter  # noqa: F401
