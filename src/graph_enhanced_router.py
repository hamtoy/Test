"""Backward compatibility - use src.routing.graph_router instead."""

import warnings

from src.routing.graph_router import *  # noqa: F403

warnings.warn(
    "Importing from 'src.graph_enhanced_router' is deprecated. "
    "Use 'from src.routing.graph_router import GraphEnhancedRouter' instead.",
    DeprecationWarning,
    stacklevel=2,
)
