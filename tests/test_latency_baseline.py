from scripts.latency_baseline import percentile, summarise


def test_percentile_interpolation():
    data = [1, 2, 3, 4]
    assert percentile(data, 0) == 1
    assert percentile(data, 100) == 4
    assert percentile(data, 50) == 2.5
    assert percentile(data, 75) == 3.25


def test_summarise_basic():
    count, min_v, max_v, mean_v, p50, p90, p99 = summarise([10, 20, 30])
    assert count == 3
    assert min_v == 10
    assert max_v == 30
    assert mean_v == 20
    assert p50 == 20
    assert p90 >= p50
