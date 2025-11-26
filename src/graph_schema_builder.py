"""Backward compatibility - use src.graph instead."""

import warnings

from src.graph import *  # noqa: F403

warnings.warn(
    "Importing from 'src.graph_schema_builder' is deprecated. "
    "Use 'from src.graph import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)
