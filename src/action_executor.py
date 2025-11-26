"""Backward compatibility - use src.features.action_executor instead."""

import warnings

from src.features.action_executor import *  # noqa: F403

warnings.warn(
    "Importing from 'src.action_executor' is deprecated. "
    "Use 'from src.features.action_executor import ActionExecutor' instead.",
    DeprecationWarning,
    stacklevel=2,
)
