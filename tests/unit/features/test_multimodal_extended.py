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


@pytest.mark.asyncio
async def test_multimodal_understanding_no_ocr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
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
        size = (10, 20)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    # Create dummy file
    dummy_img = tmp_path / "fake.png"
    dummy_img.touch()
    dummy_path = str(dummy_img)

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = await analyzer.analyze_image_deep(dummy_path)

    assert meta["has_table_chart"] is False
    assert meta["topics"] == []  # No OCR, so no topics
    assert meta["extracted_text"] == ""  # No OCR extraction
    assert fake_saved.get("path") == dummy_path


@pytest.mark.asyncio
async def test_multimodal_with_graph_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
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
        size = (100, 200)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    dummy_img = tmp_path / "test.png"
    dummy_img.touch()
    dummy_path = str(dummy_img)

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = await analyzer.analyze_image_deep(dummy_path)

    assert "path" in meta
    assert meta["path"] == dummy_path


@pytest.mark.asyncio
async def test_multimodal_no_graph(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Test multimodal analysis when no graph is available."""
    from src.features import multimodal as features_multimodal

    class _KG:
        pass  # No _graph or graph_session

    class _FakeImg:
        width = 50
        height = 50
        size = (50, 50)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    dummy_img = tmp_path / "test.png"
    dummy_img.touch()
    dummy_path = str(dummy_img)

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = await analyzer.analyze_image_deep(dummy_path)

    # Should still return metadata even without graph
    assert "path" in meta
    assert meta["path"] == dummy_path
    assert meta["topics"] == []


@pytest.mark.asyncio
async def test_multimodal_session_returns_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
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
        size = (50, 50)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    dummy_img = tmp_path / "test.png"
    dummy_img.touch()
    dummy_path = str(dummy_img)

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = await analyzer.analyze_image_deep(dummy_path)

    # Should still return metadata even when session is None
    assert "path" in meta


@pytest.mark.asyncio
async def test_multimodal_exception_handling(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
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
        size = (50, 50)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    dummy_img = tmp_path / "test.png"
    dummy_img.touch()
    dummy_path = str(dummy_img)

    analyzer = mmu.MultimodalUnderstanding(_KG())
    meta = await analyzer.analyze_image_deep(dummy_path)

    # Should still return metadata even with exception
    assert "path" in meta
    assert meta["path"] == dummy_path


def test_detect_table_chart() -> None:
    """Test table/chart detection method."""

    class _KG:
        pass

    analyzer = mmu.MultimodalUnderstanding(_KG())

    # Test with table-like text
    assert analyzer._detect_table_chart("구분: 매출액 100억") is True
    assert analyzer._detect_table_chart("합계 1000 2000 3000") is True

    # Test with no table
    assert analyzer._detect_table_chart("일반적인 텍스트입니다") is False
    assert analyzer._detect_table_chart("") is False


def test_get_mime_type() -> None:
    """Test MIME type detection by file extension."""
    from pathlib import Path

    analyzer = mmu.MultimodalUnderstanding()

    assert analyzer._get_mime_type(Path("test.png")) == "image/png"
    assert analyzer._get_mime_type(Path("test.jpg")) == "image/jpeg"
    assert analyzer._get_mime_type(Path("test.jpeg")) == "image/jpeg"
    assert analyzer._get_mime_type(Path("test.gif")) == "image/gif"
    assert analyzer._get_mime_type(Path("test.webp")) == "image/webp"
    assert analyzer._get_mime_type(Path("test.bmp")) == "image/bmp"
    assert analyzer._get_mime_type(Path("test.unknown")) == "image/png"  # default


def test_extract_topics() -> None:
    """Test topic extraction from Korean financial text."""
    analyzer = mmu.MultimodalUnderstanding()

    # Test with financial keywords
    text = "2024년 1분기 매출액 증가, 영업이익 개선. 목표주가 Buy"
    topics = analyzer._extract_topics(text)
    assert len(topics) > 0
    assert any("매출액" in t or "영업이익" in t for t in topics)

    # Test with empty text
    assert analyzer._extract_topics("") == []

    # Test with no financial keywords
    assert analyzer._extract_topics("일반적인 문장입니다") == []


@pytest.mark.asyncio
async def test_analyze_image_file_not_found() -> None:
    """Test analyze_image_deep raises error for missing file."""
    analyzer = mmu.MultimodalUnderstanding()

    with pytest.raises(FileNotFoundError):
        await analyzer.analyze_image_deep("/nonexistent/path/image.png")


@pytest.mark.asyncio
async def test_multimodal_with_llm_provider_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Test multimodal analysis handles LLM provider errors."""
    from unittest.mock import AsyncMock, MagicMock

    from src.features import multimodal as features_multimodal

    class _FakeImg:
        width = 100
        height = 100
        size = (100, 100)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    # Mock LLM provider that raises exception
    mock_provider = MagicMock()
    mock_provider.generate_vision_content_async = AsyncMock(
        side_effect=Exception("LLM error")
    )

    dummy_img = tmp_path / "test.png"
    dummy_img.write_bytes(b"fake image data")

    analyzer = mmu.MultimodalUnderstanding(llm_provider=mock_provider)
    meta = await analyzer.analyze_image_deep(str(dummy_img))

    # Should still return metadata even with LLM error
    assert "path" in meta
    assert meta["extracted_text"] == ""  # Empty due to error


@pytest.mark.asyncio
async def test_multimodal_with_llm_provider_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """Test multimodal analysis with successful LLM OCR."""
    from unittest.mock import AsyncMock, MagicMock

    from src.features import multimodal as features_multimodal

    class _FakeImg:
        width = 100
        height = 100
        size = (100, 100)

        def __enter__(self) -> "_FakeImg":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            pass

    monkeypatch.setattr(
        features_multimodal,
        "Image",
        types.SimpleNamespace(open=lambda path: _FakeImg()),
    )

    # Mock successful LLM provider
    mock_provider = MagicMock()
    mock_provider.generate_vision_content_async = AsyncMock(
        return_value="매출액 100억, 영업이익 20억"
    )

    dummy_img = tmp_path / "report.png"
    dummy_img.write_bytes(b"fake image data")

    analyzer = mmu.MultimodalUnderstanding(llm_provider=mock_provider)
    meta = await analyzer.analyze_image_deep(str(dummy_img))

    assert meta["extracted_text"] == "매출액 100억, 영업이익 20억"
    assert meta["text_density"] > 0
    assert len(meta["topics"]) > 0
