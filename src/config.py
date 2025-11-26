"""Backward compatibility - use src.config.settings instead."""

import warnings

from src.config.settings import AppConfig

warnings.warn(
    "Importing from 'src.config' module is deprecated. "
    "Use 'from src.config import AppConfig' or 'from src.config.settings import AppConfig' instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["AppConfig"]
