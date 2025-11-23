import cProfile
import pstats
import sys
from pathlib import Path


def profile_module(module_name, args=None):
    """
    Profiles the execution of a module's main execution block or run function.
    """
    # Ensure project root is on sys.path so `src.*` modules resolve when run from repo root.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    if args:
        sys.argv = [module_name] + args

    print(f"Profiling module: {module_name} with args: {args}")

    profiler = cProfile.Profile()
    profiler.enable()

    try:
        # Try to import the module and run it
        # This assumes the module does something when imported or has a main/run function we can call
        # For scripts that run on import (if __name__ == "__main__"):
        import runpy

        runpy.run_module(module_name, run_name="__main__", alter_sys=True)
    except SystemExit:
        pass
    except Exception as e:
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

        # Save full stats
        Path("profiling_results").mkdir(exist_ok=True)
        stats_file = Path(f"profiling_results/{module_name}_stats.prof")
        stats.dump_stats(stats_file)
        print(f"\nFull profiling stats saved to: {stats_file}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/auto_profile.py <module_name> [args...]")
        sys.exit(1)

    module_to_profile = sys.argv[1]
    module_args = sys.argv[2:]

    profile_module(module_to_profile, module_args)
