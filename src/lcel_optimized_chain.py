"""
Backward compatibility shim for lcel_optimized_chain.

This module has been moved to src.llm.lcel_chain.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.llm.lcel_chain import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.lcel_optimized_chain' is deprecated. "
    "Use 'from src.llm.lcel_chain import LCELOptimizedChain' instead.",
    DeprecationWarning,
    stacklevel=2,
)
