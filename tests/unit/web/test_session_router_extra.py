"""Extra tests for session router endpoints."""

from __future__ import annotations

import types

import pytest
from fastapi import HTTPException

from src.web.routers import session as session_router


def test_get_session_manager_raises_when_uninitialized() -> None:
    session_router._session_manager = None  # reset
    with pytest.raises(RuntimeError):
        session_router._get_session_manager()


@pytest.mark.asyncio
async def test_get_session_raises_when_request_missing_session() -> None:
    session_router._session_manager = types.SimpleNamespace(serialize=lambda s: {})  # type: ignore[assignment]
    request = types.SimpleNamespace(state=types.SimpleNamespace(session=None))
    with pytest.raises(HTTPException):
        await session_router.get_session(request)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_and_delete_session_success() -> None:
    fake_manager = types.SimpleNamespace(
        serialize=lambda s: {"session_id": s.session_id},
        destroy=lambda _sid: None,
    )
    session_router.set_dependencies(fake_manager)  # type: ignore[arg-type]

    fake_session = types.SimpleNamespace(session_id="s1")
    request = types.SimpleNamespace(state=types.SimpleNamespace(session=fake_session))

    result = await session_router.get_session(request)  # type: ignore[arg-type]
    assert result["session_id"] == "s1"

    result = await session_router.delete_session(request)  # type: ignore[arg-type]
    assert result["cleared"] is True
