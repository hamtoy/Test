"""Extra tests for src.agent package init lazy imports."""

from __future__ import annotations

import sys
import types

import pytest

import src.agent as agent_pkg


def test_agent_lazy_caching_import(monkeypatch: pytest.MonkeyPatch) -> None:
    if "caching" in agent_pkg.__dict__:
        del agent_pkg.__dict__["caching"]

    caching_mod = agent_pkg.caching  # triggers __getattr__
    import google.generativeai.caching as genai_caching

    assert caching_mod is genai_caching
    assert agent_pkg.caching is caching_mod
