"""Backward compatibility - use src.features.lats instead."""

import warnings

from src.features.lats import *  # noqa: F403

warnings.warn(
    "Importing from 'src.lats_searcher' is deprecated. "
    "Use 'from src.features.lats import LATSSearcher' instead.",
    DeprecationWarning,
    stacklevel=2,
)
