"""
Backward compatibility shim for ultimate_langchain_qa_system.

This module has been moved to src.llm.langchain_system.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.llm.langchain_system import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.ultimate_langchain_qa_system' is deprecated. "
    "Use 'from src.llm.langchain_system import UltimateLangChainQASystem' instead.",
    DeprecationWarning,
    stacklevel=2,
)
