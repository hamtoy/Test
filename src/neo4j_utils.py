"""Backward compatibility - use src.infra.neo4j instead."""
import warnings

from src.infra.neo4j import *

warnings.warn(
    "Importing from 'src.neo4j_utils' is deprecated. "
    "Use 'from src.infra.neo4j import SafeDriver, get_neo4j_driver_from_env' instead.",
    DeprecationWarning,
    stacklevel=2,
)
