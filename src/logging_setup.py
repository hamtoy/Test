"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.infra.logging' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.infra.logging import *  # noqa: F403

warn_deprecated(
    old_path="src.logging_setup",
    new_path="src.infra.logging",
    removal_version="v3.0",
)
