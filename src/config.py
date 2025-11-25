"""Backward compatibility - use src.config.settings instead."""
import warnings

warnings.warn(
    "Importing from 'src.config' module is deprecated. "
    "Use 'from src.config import AppConfig' or 'from src.config.settings import AppConfig' instead.",
    DeprecationWarning,
    stacklevel=2,
)

from src.config.settings import AppConfig

__all__ = ["AppConfig"]
