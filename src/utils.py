"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.infra.utils' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.infra.utils import *  # noqa: F403

warn_deprecated(
    old_path="src.utils",
    new_path="src.infra.utils",
    removal_version="v3.0",
)
