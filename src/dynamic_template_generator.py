"""
Backward compatibility shim for dynamic_template_generator.

This module has been moved to src.processing.template_generator.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.processing.template_generator import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.dynamic_template_generator' is deprecated. "
    "Use 'from src.processing.template_generator import DynamicTemplateGenerator' instead.",
    DeprecationWarning,
    stacklevel=2,
)
