import types
import pytest
from builtins import EnvironmentError

import src.semantic_analysis as sa


def test_tokenize_filters_stopwords_and_length():
    text = "The quick brown fox 그리고 it jumps"
    tokens = sa.tokenize(text)
    # "the", "it", "그리고" filtered; short words filtered
    assert "quick" in tokens and "brown" in tokens
    assert "the" not in tokens and "it" not in tokens and "그리고" not in tokens


def test_count_keywords_respects_min_freq(monkeypatch):
    monkeypatch.setattr(sa, "MIN_FREQ", 2)
    contents = ["apple banana apple", "banana cherry", "apple"]
    counter = sa.count_keywords(contents)
    assert counter["apple"] == 3
    assert "cherry" not in counter  # freq 1 < MIN_FREQ


def test_create_topics_no_keywords(monkeypatch):
    called = False

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_write(self, fn, kw):
            nonlocal called
            called = True

    driver = types.SimpleNamespace(session=lambda: _Session())
    sa.create_topics(driver, [])
    assert called is False  # no write when empty


def test_link_blocks_creates_links(monkeypatch):
    captured = []

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute_write(self, fn, rows):
            fn(None, rows)  # call lambda in code

    class _Driver:
        def session(self):
            return _Session()

    def _run(tx, rows):
        captured.extend(rows["links"])

    blocks = [
        {"id": "b1", "content": "apple orange banana"},
        {"id": "b2", "content": "grape apple"},
        {"id": None, "content": "ignored"},  # missing id
    ]
    topics = [("apple", 3), ("banana", 2)]

    monkeypatch.setattr(sa, "REL_BATCH_SIZE", 2)
    # Patch tokenization to identity split for simplicity
    monkeypatch.setattr(sa, "tokenize", lambda text: text.split())
    _orig_session_run = _Session.execute_write

    def _execute_write(self, fn, batch):
        # emulate flush calls
        _run(None, {"links": batch})

    _Session.execute_write = _execute_write  # type: ignore

    sa.link_blocks_to_topics(_Driver(), blocks, topics)

    assert {"block_id": "b1", "topic": "apple"} in captured
    assert {"block_id": "b2", "topic": "apple"} in captured
    assert {"block_id": "b1", "topic": "banana"} in captured


def test_main_env_missing_exits(monkeypatch, capsys):
    monkeypatch.setattr(
        sa, "require_env", lambda name: (_ for _ in ()).throw(EnvironmentError(name))
    )
    with pytest.raises(SystemExit):
        sa.main()
