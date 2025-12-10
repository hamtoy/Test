from typing import Any, Iterable, Sequence

def tabulate(
    tabular_data: Iterable[Sequence[Any]] | Iterable[dict[str, Any]] | dict[str, Any],
    headers: Any = ...,
    tablefmt: str = ...,
    showindex: Any = ...,
    disable_numparse: bool = ...,
    colalign: Any = ...,
    numalign: str | None = ...,
    stralign: str | None = ...,
) -> str: ...
