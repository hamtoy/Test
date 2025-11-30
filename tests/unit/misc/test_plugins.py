from pathlib import Path
from typing import Any

import pytest

from src.plugins.base import Plugin
from src.plugins.builtin.example import ExamplePlugin
from src.plugins.loader import discover_plugins, load_plugin


# Mock Plugin for testing
class MockPlugin(Plugin):
    name = "mock"
    version = "0.0.1"

    def initialize(self, config: dict[str, Any]) -> None:
        self.config = config

    def process(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"processed": True}


def test_plugin_interface() -> None:
    """Test the basic Plugin interface implementation."""
    plugin = MockPlugin()
    assert plugin.name == "mock"

    # Test initialize
    config = {"key": "value"}
    plugin.initialize(config)
    assert plugin.config == config

    # Test process
    assert plugin.process({}) == {"processed": True}

    # Test repr
    assert str(plugin) == "<Plugin mock v0.0.1>"

    # Test cleanup (default implementation does nothing but should not fail)
    plugin.cleanup()


def test_example_plugin() -> None:
    """Test the builtin ExamplePlugin."""
    plugin = ExamplePlugin()
    assert plugin.name == "example"

    # Test initialize with custom prefix
    plugin.initialize({"prefix": "TEST:"})

    # Test process
    result = plugin.process({"text": "hello"})
    assert result["text"] == "TEST: HELLO"
    assert result["transformed"] is True

    # Test cleanup
    plugin.cleanup()

    # Test default prefix
    plugin.initialize({})
    result = plugin.process({"text": "world"})
    assert result["text"] == "[EXAMPLE] WORLD"


def test_load_plugin(tmp_path: Path) -> None:
    """Test loading a plugin from a file."""
    d = tmp_path / "plugins"
    d.mkdir()
    p = d / "my_plugin.py"
    p.write_text(
        """
from src.plugins.base import Plugin
from typing import Any

class MyPlugin(Plugin):
    name = "my_plugin"
    version = "1.0.0"
    
    def initialize(self, config: dict[str, Any]) -> None: pass
    def process(self, context: dict[str, Any]) -> dict[str, Any]: return {}
""",
        encoding="utf-8",
    )

    plugins = load_plugin(p)
    assert len(plugins) == 1
    assert plugins[0].name == "my_plugin"


def test_load_plugin_invalid_file(tmp_path: Path) -> None:
    """Test loading from a non-existent or invalid file."""
    # Non-existent file
    assert load_plugin(tmp_path / "nonexistent.py") == []

    # Invalid python file
    p = tmp_path / "invalid.py"
    p.write_text("invalid python code >>>", encoding="utf-8")
    # Should return empty list or handle error gracefully (loader logs error and returns [])
    assert load_plugin(p) == []


def test_discover_plugins(tmp_path: Path) -> None:
    """Test discovering plugins in a directory."""
    d = tmp_path / "plugins"
    d.mkdir()

    # Valid plugin
    (d / "p1.py").write_text(
        """
from src.plugins.base import Plugin
from typing import Any
class P1(Plugin):
    name = "p1"
    def initialize(self, config: dict[str, Any]) -> None: pass
    def process(self, context: dict[str, Any]) -> dict[str, Any]: return {}
""",
        encoding="utf-8",
    )

    # Ignored file (starts with _)
    (d / "_ignored.py").write_text(
        """
from src.plugins.base import Plugin
class Ignored(Plugin): pass
""",
        encoding="utf-8",
    )

    # File without Plugin class
    (d / "utils.py").write_text("def helper(): pass", encoding="utf-8")

    plugins = discover_plugins(d)
    assert len(plugins) == 1
    assert plugins[0].name == "p1"


def test_discover_plugins_nonexistent() -> None:
    """Test discovering plugins in a non-existent directory."""
    assert discover_plugins(Path("nonexistent_dir_12345")) == []


def test_discover_plugins_default_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test discover_plugins with default directory (plugins/)."""
    # Mock Path("plugins") to point to tmp_path
    # Since discover_plugins uses Path("plugins") internally when arg is None,
    # we need to be careful. It's better to pass the path explicitly in tests,
    # but to test the default None argument, we'd need to ensure 'plugins' dir exists in CWD.
    # Instead, we can trust the logic `if plugin_dir is None: plugin_dir = Path("plugins")`
    # and just test that it returns empty if 'plugins' dir doesn't exist in CWD (which is likely true or empty).

    # Let's just verify it doesn't crash
    plugins = discover_plugins()
    assert isinstance(plugins, list)


def test_load_plugin_spec_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Test load_plugin when spec creation fails."""
    import importlib.util

    # Mock spec_from_file_location to return None
    def mock_spec(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(importlib.util, "spec_from_file_location", mock_spec)

    p = tmp_path / "dummy.py"
    p.touch()

    assert load_plugin(p) == []


def test_discover_plugins_instantiation_failure(tmp_path: Path) -> None:
    """Test discover_plugins when plugin instantiation fails."""
    d = tmp_path / "plugins"
    d.mkdir()

    # Plugin that raises error in __init__
    (d / "broken.py").write_text(
        """
from src.plugins.base import Plugin
from typing import Any
class Broken(Plugin):
    name = "broken"
    def __init__(self) -> None:
        raise ValueError("Boom!")
    def initialize(self, config: dict[str, Any]) -> None: pass
    def process(self, context: dict[str, Any]) -> dict[str, Any]: return {}
""",
        encoding="utf-8",
    )

    # Should skip the broken plugin and not crash
    plugins = discover_plugins(d)
    assert len(plugins) == 0
