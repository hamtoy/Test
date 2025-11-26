"""Backward compatibility - use src.features.multimodal instead."""

import warnings

from src.features.multimodal import *

warnings.warn(
    "Importing from 'src.multimodal_understanding' is deprecated. "
    "Use 'from src.features.multimodal import MultimodalUnderstanding' instead.",
    DeprecationWarning,
    stacklevel=2,
)
