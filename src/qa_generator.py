"""Backward compatibility - use src.qa.generator instead."""

from src.qa.generator import *  # noqa: F401, F403

import warnings

warnings.warn(
    "Importing from 'src.qa_generator' is deprecated. "
    "Use 'from src.qa.generator import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)
