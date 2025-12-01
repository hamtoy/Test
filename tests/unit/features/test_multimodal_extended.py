from __future__ import annotations

import sys
import types
from typing import Any, Iterator

import pytest

# module-level placeholder populated by fixture
mmu: Any = None


# Stub external deps before importing targets (with attributes for mypy)
class _StubPIL(types.ModuleType):
    class Image:
        pass


@pytest.fixture(scope="module", autouse=True)
def _stub_external_modules() -> Iterator[None]:
    """Inject stub modules and import multimodal with them, then restore."""

    mp = pytest.MonkeyPatch()
    stub_pil = _StubPIL("PIL")
    mp.setitem(sys.modules, "PIL", stub_pil)
    mp.setitem(sys.modules, "PIL.Image", stub_pil)

    global mmu
    from src.features import multimodal as multimodal_module

    mmu = multimodal_module

    yield

    # Drop the stubbed module so later tests can import real dependencies
    sys.modules.pop("src.features.multimodal", None)
    mp.undo()


def test_multimodal_understanding_no_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multimodal analysis without OCR (OCR removed - user input only)."""
    from src.features import multimodal as features_multimodal

    fake_saved: dict[str, Any] = {}

    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, _query: str, **params: Any) -> None:
            fake_saved.update(params)

    class _FakeGraph:
        def session(self) -> _FakeSession:
            return _FakeSession()

    class _KG:
        def __init__(self) -> None:
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 10
        height = 20

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("fake.png")

    assert meta["has_table_chart"] is False
    assert meta["topics"] == []  # No OCR, so no topics
    assert meta["extracted_text"] == ""  # No OCR extraction
    assert fake_saved.get("path") == "fake.png"


def test_multimodal_with_graph_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multimodal analysis with graph_session attribute."""
    from src.features import multimodal as features_multimodal

    fake_saved: dict[str, Any] = {}

    class _FakeSession:
        def __enter__(self) -> "_FakeSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, _query: str, **params: Any) -> None:
            fake_saved.update(params)

    class _KG:
        def __init__(self) -> None:
            self.graph_session = lambda: _FakeSession()

    class _FakeImg:
        width = 100
        height = 200

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    assert "path" in meta
    assert meta["path"] == "test.png"


def test_multimodal_no_graph(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multimodal analysis when no graph is available."""
    from src.features import multimodal as features_multimodal

    class _KG:
        pass  # No _graph or graph_session

    class _FakeImg:
        width = 50
        height = 50

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even without graph
    assert "path" in meta
    assert meta["path"] == "test.png"
    assert meta["topics"] == []


def test_multimodal_session_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multimodal analysis when session context returns None."""
    from src.features import multimodal as features_multimodal

    class _NoneSession:
        def __enter__(self) -> None:
            return None

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    class _FakeGraph:
        def session(self) -> _NoneSession:
            return _NoneSession()

    class _KG:
        def __init__(self) -> None:
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 50
        height = 50

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even when session is None
    assert "path" in meta


def test_multimodal_exception_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test multimodal analysis handles exceptions in graph operations."""
    from src.features import multimodal as features_multimodal

    class _ErrorSession:
        def __enter__(self) -> "_ErrorSession":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

        def run(self, _query: str, **params: Any) -> None:
            raise Exception("Neo4j connection failed")

    class _FakeGraph:
        def session(self) -> _ErrorSession:
            return _ErrorSession()

    class _KG:
        def __init__(self) -> None:
            self._graph = _FakeGraph()

    class _FakeImg:
        width = 50
        height = 50

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = analyzer.analyze_image_deep("test.png")

    # Should still return metadata even with exception
    assert "path" in meta
    assert meta["path"] == "test.png"


def test_detect_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test table detection method."""

    class _KG:
        pass

    class _FakeImg:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    result = analyzer._detect_table(_FakeImg())

    # Placeholder always returns False
    assert result is False


def test_detect_chart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test chart detection method."""

    class _KG:
        pass

    class _FakeImg:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())
    result = analyzer._detect_chart(_FakeImg())

    # Placeholder always returns False
    assert result is False
