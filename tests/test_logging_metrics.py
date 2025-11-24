from __future__ import annotations

import logging

from src.logging_setup import log_metrics


def test_log_metrics_tokens_and_cache(caplog):
    logger = logging.getLogger("metrics-test")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    with caplog.at_level(logging.INFO):
        log_metrics(
            logger,
            latency_ms=50.0,
            prompt_tokens=100,
            completion_tokens=50,
            cache_hits=2,
            cache_misses=1,
        )

    assert any("metrics" in rec.message for rec in caplog.records)
    rec = caplog.records[-1]
    metrics = rec.__dict__.get("metrics", {})
    assert metrics["latency_ms"] == 50.0
    assert metrics["prompt_tokens"] == 100
    assert metrics["completion_tokens"] == 50
    assert metrics["total_tokens"] == 150
    assert metrics["tokens_per_sec"] > 0
    assert metrics["cache_hit_ratio"] == round(2 / 3, 3)
    assert metrics["cache_hits"] == 2
    assert metrics["cache_misses"] == 1


def test_log_metrics_handles_missing(caplog):
    logger = logging.getLogger("metrics-test-missing")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    with caplog.at_level(logging.INFO):
        log_metrics(logger, latency_ms=None, cache_hits=None, cache_misses=None)

    rec = caplog.records[-1]
    metrics = rec.__dict__.get("metrics", {})
    # defaults to empty metric dict when nothing provided
    assert isinstance(metrics, dict)
