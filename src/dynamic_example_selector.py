"""
Backward compatibility shim for dynamic_example_selector.

This module has been moved to src.processing.example_selector.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.processing.example_selector import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.dynamic_example_selector' is deprecated. "
    "Use 'from src.processing.example_selector import DynamicExampleSelector' instead.",
    DeprecationWarning,
    stacklevel=2,
)
