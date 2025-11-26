"""
Backward compatibility shim for list_models.

This module has been moved to src.llm.list_models.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.llm.list_models import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.list_models' is deprecated. "
    "Use 'from src.llm.list_models' instead.",
    DeprecationWarning,
    stacklevel=2,
)
