"""Backward compatibility - use src.qa.factory instead."""

import warnings


def __getattr__(name: str) -> object:
    warnings.warn(
        f"Importing '{name}' from 'src.qa_system_factory' is deprecated. "
        "Use 'from src.qa.factory import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import factory

    return getattr(factory, name)


def __dir__() -> list[str]:
    from src.qa import factory

    return dir(factory)
