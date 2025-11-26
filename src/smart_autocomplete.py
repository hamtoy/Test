"""Backward compatibility - use src.features.autocomplete instead."""

import warnings

from src.features.autocomplete import *  # noqa: F403

warnings.warn(
    "Importing from 'src.smart_autocomplete' is deprecated. "
    "Use 'from src.features.autocomplete import SmartAutocomplete' instead.",
    DeprecationWarning,
    stacklevel=2,
)
