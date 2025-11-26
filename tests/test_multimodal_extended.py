from __future__ import annotations

import sys
import types


# Stub external deps before importing targets (with attributes for mypy)
class _StubPIL(types.ModuleType):
    class Image:  # type: ignore[valid-type]
        pass


sys.modules["PIL"] = _StubPIL("PIL")
sys.modules["PIL.Image"] = sys.modules["PIL"]


class _StubPytesseract(types.ModuleType):
    def image_to_string(self, *args, **kwargs):
        return ""


sys.modules["pytesseract"] = _StubPytesseract("pytesseract")

from src import multimodal_understanding as mmu  # noqa: E402


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
