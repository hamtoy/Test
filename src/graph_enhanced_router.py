"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.routing.graph_router' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.routing.graph_router import *  # noqa: F403

warn_deprecated(
    old_path="src.graph_enhanced_router",
    new_path="src.routing.graph_router",
    removal_version="v3.0",
)
