"""Backward compatibility - use src.infra.worker instead."""
import warnings

from src.infra.worker import *

warnings.warn(
    "Importing from 'src.worker' is deprecated. "
    "Use 'from src.infra.worker import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)
