"""Backward compatibility - use src.qa.pipeline instead."""

import warnings


def __getattr__(name: str) -> object:
    warnings.warn(
        f"Importing '{name}' from 'src.integrated_qa_pipeline' is deprecated. "
        "Use 'from src.qa.pipeline import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import pipeline

    return getattr(pipeline, name)


def __dir__() -> list[str]:
    from src.qa import pipeline

    return dir(pipeline)
