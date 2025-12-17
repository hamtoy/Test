"""Extra tests for src.main __main__ guard."""

from __future__ import annotations

import runpy
import sys
from collections.abc import Coroutine
from typing import Any

import pytest


def test_main_module_guard_invokes_asyncio_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    monkeypatch.setattr("asyncio.run", lambda _coro: calls.append("ran"))
    monkeypatch.setattr(sys, "argv", ["src.main"])

    runpy.run_module("src.main", run_name="__main__")
    assert calls == ["ran"]


def test_main_module_guard_handles_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("dotenv.load_dotenv", lambda: None)
    monkeypatch.setattr(sys, "argv", ["src.main"])

    def _raise(_coro: Coroutine[Any, Any, Any]) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("asyncio.run", _raise)

    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("src.main", run_name="__main__")
    assert excinfo.value.code == 130
