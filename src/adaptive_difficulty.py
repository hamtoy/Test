"""Backward compatibility - use src.features.difficulty instead."""

import warnings

from src.features.difficulty import *

warnings.warn(
    "Importing from 'src.adaptive_difficulty' is deprecated. "
    "Use 'from src.features.difficulty import AdaptiveDifficulty' instead.",
    DeprecationWarning,
    stacklevel=2,
)
