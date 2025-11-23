"""Summarize markdown results in ``data/outputs`` for quick comparison."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List

from rich.console import Console
from rich.table import Table

console = Console()

COST_RE = re.compile(r"\*\*Cost\*\*:\s*\$?([0-9.]+)")
TIMESTAMP_RE = re.compile(r"\*\*Timestamp\*\*:\s*([0-9T:_\-]+)")
BEST_RE = re.compile(r"\*\*Best Candidate\*\*:\s*([^\n]+)")


@dataclass
class RunSummary:
    path: Path
    cost: float | None
    timestamp: datetime | None
    raw_timestamp: str | None
    query: str | None
    best_candidate: str | None


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y%m%d_%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _extract_first_line_after(header: str, lines: List[str]) -> str | None:
    for idx, line in enumerate(lines):
        if line.strip().lower() == header.lower():
            for candidate in lines[idx + 1 :]:
                stripped = candidate.strip()
                if stripped:
                    return stripped
    return None


def parse_result_file(path: Path) -> RunSummary:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    cost_match = COST_RE.search(text)
    ts_match = TIMESTAMP_RE.search(text)
    best_match = BEST_RE.search(text)

    raw_ts = ts_match.group(1) if ts_match else None
    parsed_ts = _parse_timestamp(raw_ts)
    cost = float(cost_match.group(1)) if cost_match else None

    query_line = _extract_first_line_after("## Query", lines)
    return RunSummary(
        path=path,
        cost=cost,
        timestamp=parsed_ts,
        raw_timestamp=raw_ts,
        query=query_line,
        best_candidate=best_match.group(1).strip() if best_match else None,
    )


def load_results(directory: Path, pattern: str) -> list[RunSummary]:
    files = sorted(directory.glob(pattern))
    return [parse_result_file(path) for path in files]


def render_table(results: list[RunSummary], sort_by: str, limit: int | None) -> None:
    if not results:
        console.print("[yellow]No result files found.[/yellow]")
        return

    if sort_by == "cost":
        results.sort(key=lambda r: (r.cost is None, r.cost or 0.0), reverse=True)
    elif sort_by == "timestamp":
        results.sort(
            key=lambda r: r.timestamp or datetime.fromtimestamp(0), reverse=True
        )
    else:
        results.sort(key=lambda r: r.path.name)

    if limit:
        results = results[:limit]

    table = Table(title="Result Comparison", show_lines=False)
    table.add_column("File", style="cyan")
    table.add_column("Cost ($)", justify="right")
    table.add_column("Best", justify="center")
    table.add_column("Query", overflow="fold")
    table.add_column("Timestamp", justify="center")

    total_cost = 0.0
    cost_count = 0

    for item in results:
        cost_display = "-" if item.cost is None else f"{item.cost:.4f}"
        if item.cost is not None:
            total_cost += item.cost
            cost_count += 1

        timestamp_display = item.raw_timestamp or "-"
        query_display = item.query or "-"
        table.add_row(
            item.path.name,
            cost_display,
            item.best_candidate or "-",
            query_display,
            timestamp_display,
        )

    console.print(table)
    if cost_count:
        console.print(f"[green]Total cost (subset): ${total_cost:.4f}[/green]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare result_*.md files under data/outputs."
    )
    parser.add_argument(
        "--outputs-dir",
        type=Path,
        default=Path("data/outputs"),
        help="Directory containing result markdown files.",
    )
    parser.add_argument(
        "--pattern",
        default="result_*.md",
        help="Filename glob to match inside the outputs directory.",
    )
    parser.add_argument(
        "--sort-by",
        choices=["timestamp", "cost", "name"],
        default="timestamp",
        help="Sort results by this column.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of rows to display (0 means show all).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results = load_results(args.outputs_dir, args.pattern)
    limit = None if args.limit == 0 else args.limit
    render_table(results, args.sort_by, limit)


if __name__ == "__main__":
    main()
