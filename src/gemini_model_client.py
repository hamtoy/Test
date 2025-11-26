"""
Backward compatibility shim for gemini_model_client.

This module has been moved to src.llm.gemini.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.llm.gemini import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.gemini_model_client' is deprecated. "
    "Use 'from src.llm.gemini import GeminiModelClient' instead.",
    DeprecationWarning,
    stacklevel=2,
)
