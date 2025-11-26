"""
Backward compatibility shim for semantic_analysis.

This module has been moved to src.analysis.semantic.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.analysis.semantic import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.semantic_analysis' is deprecated. "
    "Use 'from src.analysis.semantic import SemanticAnalyzer' instead.",
    DeprecationWarning,
    stacklevel=2,
)
