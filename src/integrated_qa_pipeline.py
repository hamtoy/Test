"""Backward compatibility - use src.qa.pipeline instead."""
import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.integrated_qa_pipeline' is deprecated. "
        "Use 'from src.qa.pipeline import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import pipeline
    return getattr(pipeline, name)


def __dir__():
    from src.qa import pipeline
    return dir(pipeline)
