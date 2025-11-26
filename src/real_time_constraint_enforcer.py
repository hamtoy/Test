"""Backward compatibility - use src.infra.constraints instead."""

import warnings

from src.infra.constraints import *

warnings.warn(
    "Importing from 'src.real_time_constraint_enforcer' is deprecated. "
    "Use 'from src.infra.constraints import RealTimeConstraintEnforcer' instead.",
    DeprecationWarning,
    stacklevel=2,
)
