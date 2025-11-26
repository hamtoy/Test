"""Backward compatibility - use src.qa.generator instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.qa_generator' is deprecated. "
        "Use 'from src.qa.generator import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import generator

    return getattr(generator, name)


def __dir__():
    from src.qa import generator

    return dir(generator)
