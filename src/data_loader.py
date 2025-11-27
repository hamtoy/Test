"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.processing.loader' instead. Will be removed in v3.0.
"""

from __future__ import annotations

from src._deprecation import warn_deprecated

# Re-export all public symbols from the new location
from src.processing.loader import *  # noqa: F403, F401

warn_deprecated(
    old_path="src.data_loader",
    new_path="src.processing.loader",
    removal_version="v3.0",
)
