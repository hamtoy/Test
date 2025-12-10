# mypy: allow-untyped-decorators
"""QA 생성 모듈 패키지."""

from __future__ import annotations

from .generator import generate_single_qa
from .types import QTYPE_MAP, normalize_qtype

__all__ = [
    "QTYPE_MAP",
    "generate_single_qa",
    "normalize_qtype",
]
