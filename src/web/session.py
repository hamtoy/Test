"""Lightweight session management for the web API."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from fastapi import Request, Response
from starlette.middleware.base import RequestResponseEndpoint


@dataclass
class SessionData:
    """In-memory session representation."""

    session_id: str
    created_at: float
    last_access: float
    data: Dict[str, Any] = field(default_factory=dict)

    def touch(self) -> None:
        """Update last access time."""
        self.last_access = time.time()


class SessionManager:
    """Simple in-memory session store with TTL."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize the session manager."""
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, SessionData] = {}

    def _is_expired(self, sess: SessionData) -> bool:
        """Check if a session is expired."""
        return (time.time() - sess.last_access) > self.ttl_seconds

    def _cleanup_expired(self) -> None:
        """Remove all expired sessions."""
        expired = [sid for sid, sess in self._store.items() if self._is_expired(sess)]
        for sid in expired:
            self.destroy(sid)

    def get(self, session_id: str) -> Optional[SessionData]:
        """Fetch a session by id, returning None if missing or expired."""
        self._cleanup_expired()
        session = self._store.get(session_id)
        if session and self._is_expired(session):
            self.destroy(session_id)
            return None
        if session:
            session.touch()
        return session

    def create(self) -> SessionData:
        """Create a new session."""
        session_id = uuid.uuid4().hex
        now = time.time()
        session = SessionData(session_id=session_id, created_at=now, last_access=now)
        self._store[session_id] = session
        return session

    def get_or_create(self, session_id: Optional[str]) -> SessionData:
        """Return existing session or create a new one if missing/expired."""
        self._cleanup_expired()
        if session_id:
            existing = self.get(session_id)
            if existing:
                return existing
        return self.create()

    def destroy(self, session_id: str) -> None:
        """Remove a session if it exists."""
        self._store.pop(session_id, None)

    def serialize(self, session: SessionData) -> Dict[str, Any]:
        """Serialize session data for API responses."""
        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "last_access": session.last_access,
            "ttl_seconds": self.ttl_seconds,
            "data": session.data,
        }


def session_middleware(
    manager: SessionManager,
) -> Callable[[Request, RequestResponseEndpoint], Any]:
    """Factory to build middleware that attaches session to request.state."""

    async def _middleware(
        request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        session_id = request.cookies.get("session_id") or request.headers.get(
            "X-Session-Id"
        )
        session = manager.get_or_create(session_id)
        request.state.session = session
        response = await call_next(request)
        response.set_cookie(
            "session_id",
            session.session_id,
            httponly=True,
            samesite="strict",
            secure=True,
            max_age=manager.ttl_seconds,
        )
        return response

    return _middleware
