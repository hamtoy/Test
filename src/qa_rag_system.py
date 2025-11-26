"""Backward compatibility - use src.qa.rag_system instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.qa_rag_system' is deprecated. "
        "Use 'from src.qa.rag_system import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import rag_system

    return getattr(rag_system, name)


def __dir__():
    from src.qa import rag_system

    return dir(rag_system)
