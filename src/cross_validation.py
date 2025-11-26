"""
Backward compatibility shim for cross_validation.

This module has been moved to src.analysis.cross_validation.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.analysis.cross_validation import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.cross_validation' is deprecated. "
    "Use 'from src.analysis.cross_validation import CrossValidator' instead.",
    DeprecationWarning,
    stacklevel=2,
)
