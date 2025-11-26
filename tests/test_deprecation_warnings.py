"""Test that deprecated imports emit warnings."""

import warnings


class TestDeprecationWarnings:
    """Test that deprecated shim imports emit DeprecationWarning."""

    def test_constants_shim_warning(self):
        """Test that importing from src.constants emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.constants import ERROR_MESSAGES  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.config.constants" in str(w[0].message)

    def test_exceptions_shim_warning(self):
        """Test that importing from src.exceptions emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.exceptions import BudgetExceededError  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.config.exceptions" in str(w[0].message)

    def test_models_shim_warning(self):
        """Test that importing from src.models emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.models import WorkflowResult  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.core.models" in str(w[0].message)

    def test_utils_shim_warning(self):
        """Test that importing from src.utils emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.utils import clean_markdown_code_block  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.infra.utils" in str(w[0].message)

    def test_logging_setup_shim_warning(self):
        """Test that importing from src.logging_setup emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.logging_setup import setup_logging  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.infra.logging" in str(w[0].message)

    def test_neo4j_utils_shim_warning(self):
        """Test that importing from src.neo4j_utils emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.neo4j_utils import SafeDriver  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.infra.neo4j" in str(w[0].message)

    def test_worker_shim_warning(self):
        """Test that importing from src.worker emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.worker import OCRTask  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.infra.worker" in str(w[0].message)

    def test_data_loader_shim_warning(self):
        """Test that importing from src.data_loader emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.data_loader import load_input_data  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.processing.loader" in str(w[0].message)

    def test_qa_rag_system_shim_warning(self):
        """Test that importing from src.qa_rag_system emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Using __getattr__ pattern
            from src import qa_rag_system

            # Try to access an attribute to trigger __getattr__
            _ = qa_rag_system.QAKnowledgeGraph  # noqa: F841

            # Should have at least one warning
            assert len(w) >= 1
            assert any(issubclass(warn.category, DeprecationWarning) for warn in w)
            assert any("deprecated" in str(warn.message).lower() for warn in w)

    def test_caching_layer_shim_warning(self):
        """Test that importing from src.caching_layer emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.caching_layer import CachingLayer  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.caching.layer" in str(w[0].message)

    def test_graph_enhanced_router_shim_warning(self):
        """Test that importing from src.graph_enhanced_router emits a deprecation warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            from src.graph_enhanced_router import GraphEnhancedRouter  # noqa: F401

            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "deprecated" in str(w[0].message).lower()
            assert "src.routing.graph_router" in str(w[0].message)

    def test_config_shim_no_warning_for_package_import(self):
        """Test that importing AppConfig from src.config package (not module) works without warning."""
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
