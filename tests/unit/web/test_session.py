"""Tests for web session management."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import Request, Response

from src.web.session import SessionData, SessionManager, session_middleware


class TestSessionData:
    """Test SessionData dataclass."""

    def test_session_data_creation(self) -> None:
        """Test creating SessionData."""
        session_id = "test_session_123"
        created_at = time.time()
        last_access = time.time()

        session = SessionData(
            session_id=session_id, created_at=created_at, last_access=last_access
        )

        assert session.session_id == session_id
        assert session.created_at == created_at
        assert session.last_access == last_access
        assert session.data == {}

    def test_session_data_with_data(self) -> None:
        """Test SessionData with custom data."""
        session = SessionData(
            session_id="test",
            created_at=time.time(),
            last_access=time.time(),
            data={"user_id": "123", "preferences": {"theme": "dark"}},
        )

        assert session.data["user_id"] == "123"
        assert session.data["preferences"]["theme"] == "dark"

    def test_session_data_touch(self) -> None:
        """Test touch method updates last_access."""
        session = SessionData(
            session_id="test", created_at=time.time(), last_access=1000.0
        )

        initial_last_access = session.last_access
        time.sleep(0.01)  # Small delay
        session.touch()

        assert session.last_access > initial_last_access


class TestSessionManager:
    """Test SessionManager class."""

    def test_session_manager_init(self) -> None:
        """Test SessionManager initialization."""
        manager = SessionManager(ttl_seconds=3600)

        assert manager.ttl_seconds == 3600
        assert manager._store == {}

    def test_session_manager_default_ttl(self) -> None:
        """Test SessionManager with default TTL."""
        manager = SessionManager()

        assert manager.ttl_seconds == 3600

    def test_session_manager_create(self) -> None:
        """Test creating a new session."""
        manager = SessionManager()

        session = manager.create()

        assert session.session_id is not None
        assert session.session_id in manager._store
        assert session.created_at > 0
        assert session.last_access > 0
        assert session.data == {}

    def test_session_manager_get_existing_session(self) -> None:
        """Test getting an existing session."""
        manager = SessionManager()
        created_session = manager.create()

        retrieved_session = manager.get(created_session.session_id)

        assert retrieved_session is not None
        assert retrieved_session.session_id == created_session.session_id

    def test_session_manager_get_nonexistent_session(self) -> None:
        """Test getting a nonexistent session."""
        manager = SessionManager()

        session = manager.get("nonexistent_id")

        assert session is None

    def test_session_manager_get_expired_session(self) -> None:
        """Test getting an expired session."""
        manager = SessionManager(ttl_seconds=1)
        session = manager.create()

        # Wait for expiration
        time.sleep(1.1)

        retrieved_session = manager.get(session.session_id)

        assert retrieved_session is None
        # Session should be destroyed
        assert session.session_id not in manager._store

    def test_session_manager_get_or_create_existing(self) -> None:
        """Test get_or_create with existing session."""
        manager = SessionManager()
        created_session = manager.create()

        session = manager.get_or_create(created_session.session_id)

        assert session.session_id == created_session.session_id

    def test_session_manager_get_or_create_none_id(self) -> None:
        """Test get_or_create with None session_id."""
        manager = SessionManager()

        session = manager.get_or_create(None)

        assert session.session_id is not None
        assert session.session_id in manager._store

    def test_session_manager_get_or_create_expired(self) -> None:
        """Test get_or_create with expired session."""
        manager = SessionManager(ttl_seconds=1)
        old_session = manager.create()
        old_id = old_session.session_id

        # Wait for expiration
        time.sleep(1.1)

        new_session = manager.get_or_create(old_id)

        assert new_session.session_id != old_id

    def test_session_manager_destroy(self) -> None:
        """Test destroying a session."""
        manager = SessionManager()
        session = manager.create()

        manager.destroy(session.session_id)

        assert session.session_id not in manager._store
        assert manager.get(session.session_id) is None

    def test_session_manager_destroy_nonexistent(self) -> None:
        """Test destroying a nonexistent session."""
        manager = SessionManager()

        # Should not raise exception
        manager.destroy("nonexistent_id")

    def test_session_manager_serialize(self) -> None:
        """Test serializing session data."""
        manager = SessionManager(ttl_seconds=1800)
        session = SessionData(
            session_id="test_123",
            created_at=1000.0,
            last_access=2000.0,
            data={"key": "value"},
        )

        serialized = manager.serialize(session)

        assert serialized["session_id"] == "test_123"
        assert serialized["created_at"] == 1000.0
        assert serialized["last_access"] == 2000.0
        assert serialized["ttl_seconds"] == 1800
        assert serialized["data"] == {"key": "value"}

    def test_session_manager_cleanup_expired(self) -> None:
        """Test cleanup of expired sessions."""
        manager = SessionManager(ttl_seconds=1)
        
        # Create multiple sessions
        session1 = manager.create()
        session2 = manager.create()

        # Wait for expiration
        time.sleep(1.1)

        # Trigger cleanup via get
        manager.get("any_id")

        assert session1.session_id not in manager._store
        assert session2.session_id not in manager._store


class TestSessionMiddleware:
    """Test session middleware."""

    @pytest.mark.asyncio
    async def test_session_middleware_new_session(self) -> None:
        """Test middleware creates new session when none exists."""
        manager = SessionManager()
        middleware = session_middleware(manager)

        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        mock_request.headers = {}
        mock_request.state = Mock()

        mock_response = Mock(spec=Response)
        mock_call_next = AsyncMock(return_value=mock_response)

        result = await middleware(mock_request, mock_call_next)

        assert result is mock_response
        assert hasattr(mock_request.state, "session")
        mock_response.set_cookie.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_middleware_existing_cookie(self) -> None:
        """Test middleware uses existing session from cookie."""
        manager = SessionManager()
        existing_session = manager.create()
        middleware = session_middleware(manager)

        mock_request = Mock(spec=Request)
        mock_request.cookies = {"session_id": existing_session.session_id}
        mock_request.headers = {}
        mock_request.state = Mock()

        mock_response = Mock(spec=Response)
        mock_call_next = AsyncMock(return_value=mock_response)

        await middleware(mock_request, mock_call_next)

        assert mock_request.state.session.session_id == existing_session.session_id

    @pytest.mark.asyncio
    async def test_session_middleware_existing_header(self) -> None:
        """Test middleware uses existing session from header."""
        manager = SessionManager()
        existing_session = manager.create()
        middleware = session_middleware(manager)

        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        mock_request.headers = {"X-Session-Id": existing_session.session_id}
        mock_request.state = Mock()

        mock_response = Mock(spec=Response)
        mock_call_next = AsyncMock(return_value=mock_response)

        await middleware(mock_request, mock_call_next)

        assert mock_request.state.session.session_id == existing_session.session_id
