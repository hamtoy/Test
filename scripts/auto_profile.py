"""Lightweight cProfile runner for modules (works like `python -m`)."""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path
from typing import Iterable, List


def _normalize_module_args(raw_args: Iterable[str]) -> list[str]:
    """Drop a leading `--` separator if provided."""
    args = list(raw_args)
    if args and args[0] == "--":
        return args[1:]
    return args


def profile_module(module_name: str, args: List[str] | None = None) -> None:
    """Profile a module as if run via `python -m <module_name>`."""
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if args:
        sys.argv = [module_name] + args

    print(f"Profiling module: {module_name} with args: {args}")

    profiler = cProfile.Profile()
    profiler.enable()

    try:
        import runpy

        runpy.run_module(module_name, run_name="__main__", alter_sys=True)
    except SystemExit:
        pass
    except Exception as e:  # noqa: BLE001
        print(f"Error running module: {e}")
    finally:
        profiler.disable()

        stats = pstats.Stats(profiler)
        stats.strip_dirs()
        stats.sort_stats("cumtime")

        print("\n" + "=" * 50)
        print("TOP 20 PERFORMANCE BOTTLENECKS (Cumulative Time)")
        print("=" * 50)
        stats.print_stats(20)

        Path("profiling_results").mkdir(exist_ok=True)
        stats_file = Path(f"profiling_results/{module_name}_stats.prof")
        stats.dump_stats(stats_file)
        print(f"\nFull profiling stats saved to: {stats_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile a module with cProfile (runs like `python -m <module>`)."
    )
    parser.add_argument(
        "module",
        help="Module path (e.g., src.main).",
    )
    parser.add_argument(
        "module_args",
        nargs=argparse.REMAINDER,
        help="Args forwarded to the module; prefix with `--` to separate if needed.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    module_args = _normalize_module_args(args.module_args)
    profile_module(args.module, module_args)
