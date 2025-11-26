"""
Backward compatibility shim for advanced_context_augmentation.

This module has been moved to src.processing.context_augmentation.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.processing.context_augmentation import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.advanced_context_augmentation' is deprecated. "
    "Use 'from src.processing.context_augmentation import AdvancedContextAugmentation' instead.",
    DeprecationWarning,
    stacklevel=2,
)
