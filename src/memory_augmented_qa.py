"""Backward compatibility - use src.qa.memory_augmented instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.memory_augmented_qa' is deprecated. "
        "Use 'from src.qa.memory_augmented import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import memory_augmented

    return getattr(memory_augmented, name)


def __dir__():
    from src.qa import memory_augmented

    return dir(memory_augmented)
