"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.qa.rag_system' instead. Will be removed in v3.0.
"""

from typing import Any

from src._deprecation import warn_deprecated


def __getattr__(name: str) -> Any:
    warn_deprecated(
        old_path="src.qa_rag_system",
        new_path="src.qa.rag_system",
        removal_version="v3.0",
    )
    from src.qa import rag_system

    return getattr(rag_system, name)


def __dir__() -> list[str]:
    from src.qa import rag_system

    return dir(rag_system)
