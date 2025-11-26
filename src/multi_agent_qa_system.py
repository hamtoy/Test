"""Backward compatibility - use src.qa.multi_agent instead."""

import warnings


def __getattr__(name):
    warnings.warn(
        f"Importing '{name}' from 'src.multi_agent_qa_system' is deprecated. "
        "Use 'from src.qa.multi_agent import ...' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from src.qa import multi_agent

    return getattr(multi_agent, name)


def __dir__():
    from src.qa import multi_agent

    return dir(multi_agent)
