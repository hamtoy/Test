"""Compatibility shim for import migration helpers."""

from scripts.migration.migrate_imports import (
    IMPORT_MAPPINGS,
    MigrationResult,
    collect_files,
    generate_diff,
    main,
    migrate_file,
    should_exclude,
)

__all__ = [
    "IMPORT_MAPPINGS",
    "MigrationResult",
    "collect_files",
    "generate_diff",
    "main",
    "migrate_file",
    "should_exclude",
]
