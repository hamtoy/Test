import argparse
import re
import statistics
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from rich.console import Console
from rich.table import Table

LATENCY_PATTERN = re.compile(r"API latency:\s*([0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)


def extract_latencies(paths: Iterable[Path]) -> List[float]:
    latencies: List[float] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                match = LATENCY_PATTERN.search(line)
                if match:
                    try:
                        latencies.append(float(match.group(1)))
                    except ValueError:
                        continue
    return latencies


def percentile(sorted_values: Sequence[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return sorted_values[0]
    if p >= 100:
        return sorted_values[-1]
    k = (len(sorted_values) - 1) * (p / 100)
    lower = int(k)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    frac = k - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * frac


def summarise(latencies: List[float]) -> Tuple[int, float, float, float, float, float, float]:
    if not latencies:
        return 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    latencies.sort()
    return (
        len(latencies),
        min(latencies),
        max(latencies),
        statistics.fmean(latencies),
        percentile(latencies, 50),
        percentile(latencies, 90),
        percentile(latencies, 99),
    )


def print_table(
    count: int,
    min_v: float,
    max_v: float,
    mean_v: float,
    p50: float,
    p90: float,
    p99: float,
) -> None:
    table = Table(title="API Latency (ms)")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Count", str(count))
    table.add_row("Min", f"{min_v:.2f}")
    table.add_row("Mean", f"{mean_v:.2f}")
    table.add_row("Max", f"{max_v:.2f}")
    table.add_row("p50", f"{p50:.2f}")
    table.add_row("p90", f"{p90:.2f}")
    table.add_row("p99", f"{p99:.2f}")
    Console().print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute latency percentiles from log files.")
    parser.add_argument(
        "--log-file",
        action="append",
        default=[],
        help="Path to log file (can be repeated). Defaults to LOG_FILE env or app.log",
    )
    parser.add_argument(
        "--default-log",
        default="app.log",
        help="Default log file when --log-file is not provided.",
    )
    args = parser.parse_args()

    log_files = [Path(p) for p in args.log_file] if args.log_file else [Path(args.default_log)]
    latencies = extract_latencies(log_files)
    if not latencies:
        Console().print("[yellow]No latency entries found.[/yellow]")
        return
    summary = summarise(latencies)
    print_table(*summary)


if __name__ == "__main__":
    main()
