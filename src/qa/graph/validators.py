"""Validation helpers for graph-related payloads."""

from __future__ import annotations

import logging
from typing import Any

from checks.validate_session import validate_turns

logger = logging.getLogger(__name__)


def validate_session_structure(session: dict[str, Any]) -> dict[str, Any]:
    """Validate session structure using shared validation logic."""
    from scripts.build_session import SessionContext

    turns = session.get("turns", [])
    if not turns:
        return {"ok": False, "issues": ["turns가 비어있습니다."]}

    ctx_kwargs = session.get("context", {})
    try:
        ctx = SessionContext(**ctx_kwargs)
        res: dict[str, Any] = validate_turns([type("T", (), t) for t in turns], ctx)
        return res
    except (TypeError, ValueError) as exc:
        return {"ok": False, "issues": [f"컨텍스트 생성 실패: {exc}"]}
    except (AttributeError, KeyError, RuntimeError) as exc:
        return {"ok": False, "issues": [f"컨텍스트 검증 실패: {exc}"]}
