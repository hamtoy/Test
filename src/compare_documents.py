"""
Backward compatibility shim for compare_documents.

This module has been moved to src.analysis.document_compare.
This file provides backward compatibility by re-exporting from the new location.
"""

from __future__ import annotations

import warnings

# Re-export all public symbols from the new location
from src.analysis.document_compare import *  # noqa: F403, F401

warnings.warn(
    "Importing from 'src.compare_documents' is deprecated. "
    "Use 'from src.analysis.document_compare import DocumentComparer' instead.",
    DeprecationWarning,
    stacklevel=2,
)
