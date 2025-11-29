from scripts.latency_baseline import percentile, summarise
from scripts.latency_baseline import extract_latencies
from pathlib import Path


def test_percentile_interpolation() -> None:
    data = [1, 2, 3, 4]
    assert percentile(data, 0) == 1
    assert percentile(data, 100) == 4
    assert percentile(data, 50) == 2.5
    assert percentile(data, 75) == 3.25


def test_summarise_basic() -> None:
    count, min_v, max_v, mean_v, p50, p90, p99 = summarise([10, 20, 30])
    assert count == 3
    assert min_v == 10
    assert max_v == 30
    assert mean_v == 20
    assert p50 == 20
    assert p90 >= p50


def test_extract_latencies(tmp_path: Path) -> None:
    log = tmp_path / "app.log"
    log.write_text(
        "\n".join(
            [
                "INFO API latency: 10.5 ms",
                "INFO something else",
                "INFO API latency: 20 ms",
            ]
        ),
        encoding="utf-8",
    )
    found = extract_latencies([log])
    assert found == [10.5, 20.0]
