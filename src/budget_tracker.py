"""Backward compatibility - use src.infra.budget instead."""

import warnings

from src.infra.budget import *  # noqa: F403

warnings.warn(
    "Importing from 'src.budget_tracker' is deprecated. "
    "Use 'from src.infra.budget import BudgetTracker' instead.",
    DeprecationWarning,
    stacklevel=2,
)
