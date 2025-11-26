"""Backward compatibility - use src.infra.logging instead."""
import warnings

from src.infra.logging import *

warnings.warn(
    "Importing from 'src.logging_setup' is deprecated. "
    "Use 'from src.infra.logging import setup_logging, log_metrics' instead.",
    DeprecationWarning,
    stacklevel=2,
)
