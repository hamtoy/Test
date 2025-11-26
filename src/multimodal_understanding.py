"""Backward compatibility - use src.features.multimodal instead."""

import warnings

from src.features.multimodal import *  # noqa: F403

warnings.warn(
    "Importing from 'src.multimodal_understanding' is deprecated. "
    "Use 'from src.features.multimodal import MultimodalUnderstanding' instead.",
    DeprecationWarning,
    stacklevel=2,
)
