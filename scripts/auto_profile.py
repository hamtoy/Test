"""Lightweight cProfile runner for modules (works like `python -m`).

Supports multiple profiling modes:
- BASIC: Simple cProfile with cumulative time sorting
- AUTO: Auto-detects bottlenecks and provides recommendations
- DETAILED: Full call graph with statistics
"""

from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path
from typing import Iterable, List, Literal

ProfileMode = Literal["BASIC", "AUTO", "DETAILED"]


def _normalize_module_args(raw_args: Iterable[str]) -> list[str]:
    """Drop a leading `--` separator if provided."""
    args = list(raw_args)
    if args and args[0] == "--":
        return args[1:]
    return args


def _analyze_bottlenecks(stats: pstats.Stats) -> List[str]:
    """Analyze profiling stats and identify bottlenecks.

    Returns:
        List of recommendation strings
    """
    recommendations: List[str] = []
    stats_list = stats.get_stats_profile().func_profiles

    # Sort by cumulative time
    sorted_funcs = sorted(stats_list.items(), key=lambda x: x[1].cumtime, reverse=True)

    total_time = sum(p.cumtime for _, p in sorted_funcs[:5])

    for func_name, profile in sorted_funcs[:5]:
        if profile.cumtime > 0.1:  # More than 100ms
            pct = (profile.cumtime / max(total_time, 0.001)) * 100
            recommendations.append(
                f"  - {func_name}: {profile.cumtime:.3f}s ({pct:.1f}% of top-5 time)"
            )

    return recommendations


def profile_module(
    module_name: str,
    args: List[str] | None = None,
    mode: ProfileMode = "BASIC",
) -> None:
    """Profile a module as if run via `python -m <module_name>`.

    Args:
        module_name: Module path (e.g., src.main)
        args: Arguments to pass to the module
        mode: Profiling mode - BASIC, AUTO, or DETAILED
    """
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if args:
        sys.argv = [module_name] + args

    print(f"Profiling module: {module_name} with args: {args}")
    print(f"Mode: {mode}")

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

        if mode == "AUTO":
            # Auto mode: Analyze and provide recommendations
            stats.sort_stats("cumtime")
            print("\n" + "=" * 50)
            print("AUTO PROFILING ANALYSIS")
            print("=" * 50)

            print("\nTOP 20 PERFORMANCE BOTTLENECKS (Cumulative Time)")
            print("-" * 50)
            stats.print_stats(20)

            print("\n" + "=" * 50)
            print("BOTTLENECK RECOMMENDATIONS")
            print("=" * 50)
            recommendations = _analyze_bottlenecks(stats)
            if recommendations:
                print("Functions consuming most time:")
                for rec in recommendations:
                    print(rec)
            else:
                print("No significant bottlenecks detected.")

            # Additional call graph analysis
            print("\n" + "=" * 50)
            print("CALL GRAPH ANALYSIS (Callers)")
            print("=" * 50)
            stats.print_callers(10)

        elif mode == "DETAILED":
            # Detailed mode: Full statistics
            print("\n" + "=" * 50)
            print("DETAILED PROFILING RESULTS")
            print("=" * 50)

            print("\nBy Cumulative Time:")
            stats.sort_stats("cumtime")
            stats.print_stats(30)

            print("\nBy Total Time:")
            stats.sort_stats("tottime")
            stats.print_stats(30)

            print("\nCall Graph (Callers):")
            stats.print_callers(20)

            print("\nCall Graph (Callees):")
            stats.print_callees(20)

        else:
            # Basic mode: Simple output
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
        "--mode",
        choices=["BASIC", "AUTO", "DETAILED"],
        default="BASIC",
        help="Profiling mode: BASIC (simple), AUTO (with recommendations), DETAILED (full)",
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
    profile_module(args.module, module_args, args.mode)
