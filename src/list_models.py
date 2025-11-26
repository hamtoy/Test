"""Backward compatibility - use src.llm.list_models instead."""

import warnings

warnings.warn(
    "Importing from 'src.list_models' is deprecated. "
    "Use 'from src.llm.list_models import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.llm.list_models import *  # noqa: F401, F403, E402
