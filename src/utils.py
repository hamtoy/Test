"""Backward compatibility - use src.infra.utils instead."""

import warnings

from src.infra.utils import *

warnings.warn(
    "Importing from 'src.utils' is deprecated. "
    "Use 'from src.infra.utils import ...' instead.",
    DeprecationWarning,
    stacklevel=2,
)
