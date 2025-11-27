"""
⚠️ DEPRECATED: This module is deprecated since v2.0.
Use 'src.infra.neo4j' instead. Will be removed in v3.0.
"""

from src._deprecation import warn_deprecated
from src.infra.neo4j import *  # noqa: F403

warn_deprecated(
    old_path="src.neo4j_utils",
    new_path="src.infra.neo4j",
    removal_version="v3.0",
)
