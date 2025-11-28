from __future__ import annotations

import sys
import types


# Stub external deps before importing targets (with attributes for mypy)
class _StubPIL(types.ModuleType):
    class Image:
        pass


sys.modules["PIL"] = _StubPIL("PIL")
sys.modules["PIL.Image"] = sys.modules["PIL"]


class _StubPytesseract(types.ModuleType):
    def image_to_string(self, *args, **kwargs):
        return ""


sys.modules["pytesseract"] = _StubPytesseract("pytesseract")

from src.features import multimodal as mmu  # noqa: E402


def test_multimodal_understanding_uses_fakes(monkeypatch):
    # Import the actual multimodal module to patch the right namespace
    from src.features import multimodal as features_multimodal

    fake_saved = {}

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, _query, **params):
            fake_saved.update(params)

    class _FakeGraph:
        def session(self):
            return _FakeSession()

    class _KG:
        def __init__(self):
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 10
        height = 20

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )
    monkeypatch.setattr(
        features_multimodal,
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda img, lang=None: "alpha beta beta"),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("fake.png")

    assert meta["has_table_chart"] is False
    assert sorted(meta["topics"]) == ["alpha", "beta"]
    assert fake_saved.get("path") == "fake.png"


def test_multimodal_with_graph_session(monkeypatch):
    """Test multimodal analysis with graph_session attribute."""
    from src.features import multimodal as features_multimodal

    fake_saved = {}

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, _query, **params):
            fake_saved.update(params)

    class _KG:
        def __init__(self):
            self.graph_session = lambda: _FakeSession()

    class _FakeImg:
        width = 100
        height = 200

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )
    monkeypatch.setattr(
        features_multimodal,
        "pytesseract",
        types.SimpleNamespace(
            image_to_string=lambda img, lang=None: "test text content"
        ),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    assert "path" in meta
    assert meta["path"] == "test.png"


def test_multimodal_no_graph(monkeypatch):
    """Test multimodal analysis when no graph is available."""
    from src.features import multimodal as features_multimodal

    class _KG:
        pass  # No _graph or graph_session

    class _FakeImg:
        width = 50
        height = 50

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )
    monkeypatch.setattr(
        features_multimodal,
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda img, lang=None: "word word word"),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even without graph
    assert "path" in meta
    assert meta["path"] == "test.png"
    assert meta["topics"] == ["word"]


def test_multimodal_session_returns_none(monkeypatch):
    """Test multimodal analysis when session context returns None."""
    from src.features import multimodal as features_multimodal

    class _NoneSession:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeGraph:
        def session(self):
            return _NoneSession()

    class _KG:
        def __init__(self):
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 50
        height = 50

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )
    monkeypatch.setattr(
        features_multimodal,
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda img, lang=None: "sample text"),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even when session is None
    assert "path" in meta


def test_multimodal_exception_handling(monkeypatch):
    """Test multimodal analysis handles exceptions in graph operations."""
    from src.features import multimodal as features_multimodal

    class _ErrorSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def run(self, _query, **params):
            raise Exception("Neo4j connection failed")

    class _FakeGraph:
        def session(self):
            return _ErrorSession()

    class _KG:
        def __init__(self):
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 50
        height = 50

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )
    monkeypatch.setattr(
        features_multimodal,
        "pytesseract",
        types.SimpleNamespace(image_to_string=lambda img, lang=None: "test"),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even with exception
    assert "path" in meta
    assert meta["path"] == "test.png"


def test_detect_table(monkeypatch):
    """Test table detection method."""

    class _KG:
        pass

    class _FakeImg:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    result = analyzer._detect_table(_FakeImg())

    # Placeholder always returns False
    assert result is False


def test_detect_chart(monkeypatch):
    """Test chart detection method."""

    class _KG:
        pass

    class _FakeImg:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    result = analyzer._detect_chart(_FakeImg())

    # Placeholder always returns False
    assert result is False


def test_extract_topics_empty_text():
    """Test topic extraction with empty text."""

    class _KG:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    topics = analyzer._extract_topics("")

    assert topics == []


def test_extract_topics_short_words():
    """Test topic extraction filters out short words."""

    class _KG:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    topics = analyzer._extract_topics("a b c ab cd ef")

    # Only words with len > 2 are kept
    assert topics == []


def test_extract_topics_frequency():
    """Test topic extraction returns most common words."""

    class _KG:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    topics = analyzer._extract_topics("apple banana apple cherry apple banana date")

    # Most common first (max 5)
    assert "apple" in topics
    assert "banana" in topics
