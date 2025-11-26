"""Backward compatibility - use src.infra.health instead."""

import warnings

from src.infra.health import *  # noqa: F403

warnings.warn(
    "Importing from 'src.health_check' is deprecated. "
    "Use 'from src.infra.health import health_check' instead.",
    DeprecationWarning,
    stacklevel=2,
)
