"""Backward compatibility - use src.qa.quality instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.integrated_quality_system' is deprecated. "
        "Use 'from src.qa.quality import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import quality

    return getattr(quality, name)


def __dir__():
    from src.qa import quality

    return dir(quality)
