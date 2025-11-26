"""
Backward compatibility shim for data_loader.

This module has been moved to src.processing.loader.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.processing.loader import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.data_loader' is deprecated. "
    "Use 'from src.processing.loader import DataLoader' instead.",
    DeprecationWarning,
    stacklevel=2,
)
