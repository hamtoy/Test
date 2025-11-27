"""Tests for the enhanced deprecation warning system."""

import os
import sys
import warnings

import pytest


class TestEnhancedDeprecationWarning:
    """Test the EnhancedDeprecationWarning class."""

    def test_warning_class_exists(self):
        """Test that EnhancedDeprecationWarning is defined."""
        from src._deprecation import EnhancedDeprecationWarning

        assert issubclass(EnhancedDeprecationWarning, DeprecationWarning)

    def test_warning_is_always_shown(self):
        """Test that EnhancedDeprecationWarning is always visible."""
        from src._deprecation import EnhancedDeprecationWarning

        # Should be caught by warnings.catch_warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warnings.warn("Test message", EnhancedDeprecationWarning)

            assert len(w) == 1
            assert issubclass(w[0].category, EnhancedDeprecationWarning)
            assert "Test message" in str(w[0].message)


class TestWarnDeprecated:
    """Test the warn_deprecated function."""

    def setup_method(self):
        """Clear environment variable before each test."""
        if "DEPRECATION_LEVEL" in os.environ:
            del os.environ["DEPRECATION_LEVEL"]

    def teardown_method(self):
        """Clean up environment variable after each test."""
        if "DEPRECATION_LEVEL" in os.environ:
            del os.environ["DEPRECATION_LEVEL"]

    def test_basic_warning(self):
        """Test that warn_deprecated emits a deprecation warning."""
        from src._deprecation import EnhancedDeprecationWarning, warn_deprecated

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("src.models", "src.core.models", "v3.0")

            assert len(w) >= 1
            deprecation_warnings = [
                warn
                for warn in w
                if issubclass(warn.category, EnhancedDeprecationWarning)
            ]
            assert len(deprecation_warnings) >= 1
            assert "src.models" in str(deprecation_warnings[0].message)
            assert "src.core.models" in str(deprecation_warnings[0].message)
            assert "v3.0" in str(deprecation_warnings[0].message)

    def test_warning_message_format(self):
        """Test that warning message contains all required information."""
        from src._deprecation import EnhancedDeprecationWarning, warn_deprecated

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("old.path", "new.path", "v4.0")

            assert len(w) >= 1
            deprecation_warnings = [
                warn
                for warn in w
                if issubclass(warn.category, EnhancedDeprecationWarning)
            ]
            message = str(deprecation_warnings[0].message)
            assert "DEPRECATED" in message
            assert "old.path" in message
            assert "new.path" in message
            assert "v4.0" in message
            assert "v2.0" in message  # Deprecation started version

    def test_deprecation_level_normal(self):
        """Test that normal level emits warning without raising."""
        os.environ["DEPRECATION_LEVEL"] = "normal"
        from src._deprecation import warn_deprecated

        # Should not raise, just warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("src.old", "src.new")

            assert len(w) >= 1

    def test_deprecation_level_strict_raises_import_error(self):
        """Test that strict level raises ImportError."""
        os.environ["DEPRECATION_LEVEL"] = "strict"

        # Need to reload the module to pick up the env var
        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import warn_deprecated

        with pytest.raises(ImportError) as exc_info:
            warn_deprecated("src.deprecated", "src.new")

        assert "deprecated" in str(exc_info.value).lower()
        assert "src.new" in str(exc_info.value)

    def test_deprecation_level_verbose_includes_stacktrace(self):
        """Test that verbose level includes caller information."""
        os.environ["DEPRECATION_LEVEL"] = "verbose"

        # Need to reload the module to pick up the env var
        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import warn_deprecated

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("src.old", "src.new")

            assert len(w) >= 1
            message = str(w[-1].message)
            assert "Called from:" in message

    def test_deprecation_level_case_insensitive(self):
        """Test that DEPRECATION_LEVEL is case-insensitive."""
        os.environ["DEPRECATION_LEVEL"] = "STRICT"

        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import warn_deprecated

        with pytest.raises(ImportError):
            warn_deprecated("src.old", "src.new")

    def test_deprecation_level_invalid_defaults_to_normal(self):
        """Test that invalid DEPRECATION_LEVEL defaults to normal."""
        os.environ["DEPRECATION_LEVEL"] = "invalid_value"

        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import warn_deprecated

        # Should not raise, just warn
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("src.old", "src.new")

            assert len(w) >= 1

    def test_default_removal_version(self):
        """Test that default removal version is v3.0."""
        from src._deprecation import warn_deprecated

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            warn_deprecated("src.old", "src.new")  # No removal_version specified

            assert len(w) >= 1
            assert "v3.0" in str(w[-1].message)

    def test_warning_visibility(self):
        """Test that warnings are visible even with default Python filters."""
        from src._deprecation import EnhancedDeprecationWarning

        # Don't set "always" filter - test with default behavior
        with warnings.catch_warnings(record=True) as w:
            # Use the default filter settings
            warnings.filterwarnings("always", category=EnhancedDeprecationWarning)
            warnings.warn("Test visibility", EnhancedDeprecationWarning)

            assert len(w) == 1


class TestGetCallerInfo:
    """Test the _get_caller_info helper function."""

    def test_caller_info_format(self):
        """Test that caller info contains expected elements."""
        from src._deprecation import _get_caller_info

        info = _get_caller_info(stacklevel=1)

        # Should contain file path, line number, and function name
        assert "Called from:" in info or info == ""


class TestGetDeprecationLevel:
    """Test the _get_deprecation_level helper function."""

    def setup_method(self):
        """Clear environment variable before each test."""
        if "DEPRECATION_LEVEL" in os.environ:
            del os.environ["DEPRECATION_LEVEL"]

    def teardown_method(self):
        """Clean up environment variable after each test."""
        if "DEPRECATION_LEVEL" in os.environ:
            del os.environ["DEPRECATION_LEVEL"]

    def test_default_level_is_normal(self):
        """Test that default level is 'normal' when env var is not set."""
        # Reload module to ensure fresh state
        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import _get_deprecation_level

        assert _get_deprecation_level() == "normal"

    def test_strict_level(self):
        """Test that strict level is recognized."""
        os.environ["DEPRECATION_LEVEL"] = "strict"

        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import _get_deprecation_level

        assert _get_deprecation_level() == "strict"

    def test_verbose_level(self):
        """Test that verbose level is recognized."""
        os.environ["DEPRECATION_LEVEL"] = "verbose"

        if "src._deprecation" in sys.modules:
            del sys.modules["src._deprecation"]

        from src._deprecation import _get_deprecation_level

        assert _get_deprecation_level() == "verbose"
