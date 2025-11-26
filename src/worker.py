"""Backward compatibility - use src.infra.worker instead."""

import warnings

from src.infra.worker import *  # noqa: F403

warnings.warn(
    "Importing from 'src.worker' is deprecated. "
    "Use 'from src.infra.worker import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)
