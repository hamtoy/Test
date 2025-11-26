"""Backward compatibility - use src.infra.callbacks instead."""

import warnings

from src.infra.callbacks import *  # noqa: F403

warnings.warn(
    "Importing from 'src.custom_callback' is deprecated. "
    "Use 'from src.infra.callbacks import CustomCallback' instead.",
    DeprecationWarning,
    stacklevel=2,
)
