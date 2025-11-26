"""Backward compatibility - use src.features.self_correcting instead."""

import warnings

from src.features.self_correcting import *  # noqa: F403

warnings.warn(
    "Importing from 'src.self_correcting_chain' is deprecated. "
    "Use 'from src.features.self_correcting import SelfCorrectingChain' instead.",
    DeprecationWarning,
    stacklevel=2,
)
