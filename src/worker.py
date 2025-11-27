"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.infra.worker' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.infra.worker import *  # noqa: F403

warn_deprecated(
    old_path="src.worker",
    new_path="src.infra.worker",
    removal_version="v3.0",
)
