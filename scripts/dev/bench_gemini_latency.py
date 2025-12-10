"""Quick latency benchmark for GeminiModelClient.

Runs a short prompt multiple times (optionally with limited concurrency)
and prints basic latency statistics. Requires GEMINI_API_KEY in the env.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time
from typing import Iterable, List

from src.llm.gemini import GeminiModelClient


def _run_once(client: GeminiModelClient, prompt: str, temperature: float) -> float:
    """Execute a single generation and return latency in ms."""
    start = time.perf_counter()
    _ = client.generate(prompt, temperature=temperature)
    return (time.perf_counter() - start) * 1000


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    k = (len(values_sorted) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(values_sorted) - 1)
    if f == c:
        return values_sorted[f]
    return values_sorted[f] + (k - f) * (values_sorted[c] - values_sorted[f])


def _summarise(latencies: Iterable[float]) -> dict[str, float]:
    data = list(latencies)
    if not data:
        return {k: 0.0 for k in ["count", "min", "mean", "p50", "p90", "p99", "max"]}
    return {
        "count": float(len(data)),
        "min": min(data),
        "mean": statistics.fmean(data),
        "p50": _percentile(data, 50),
        "p90": _percentile(data, 90),
        "p99": _percentile(data, 99),
        "max": max(data),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Gemini latency benchmark")
    parser.add_argument(
        "--prompt",
        default="한 문장으로 간단히 요약해 주세요.",
        help="Prompt text to send to Gemini.",
    )
    parser.add_argument(
        "-n",
        "--iterations",
        type=int,
        default=5,
        help="Number of measured iterations.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warmup runs (not measured).",
    )
    parser.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=1,
        help="Number of concurrent workers (each with its own client).",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Generation temperature.",
    )
    args = parser.parse_args()

    # Single client for sequential runs to avoid re-init overhead.
    shared_client = GeminiModelClient()

    # Warmup (sequential)
    for _ in range(max(args.warmup, 0)):
        _run_once(shared_client, args.prompt, args.temperature)

    latencies: list[float] = []
    if args.concurrency <= 1:
        for _ in range(args.iterations):
            latencies.append(_run_once(shared_client, args.prompt, args.temperature))
    else:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.concurrency
        ) as executor:
            futures = [
                executor.submit(
                    _run_once, GeminiModelClient(), args.prompt, args.temperature
                )
                for _ in range(args.iterations)
            ]
            for fut in concurrent.futures.as_completed(futures):
                latencies.append(fut.result())

    stats = _summarise(latencies)
    print("\nGemini latency (ms)")
    for key in ["count", "min", "mean", "p50", "p90", "p99", "max"]:
        val = stats[key]
        if key == "count":
            print(f"- {key:>4}: {int(val)}")
        else:
            print(f"- {key:>4}: {val:7.2f}")


if __name__ == "__main__":
    main()
