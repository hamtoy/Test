"""Prometheus metrics exporter for monitoring.

Exports metrics in Prometheus format for integration with
monitoring stacks like Grafana + Prometheus.

Metrics exported:
- api_request_latency_seconds (histogram)
- api_requests_total (counter)
- token_usage_total (counter)
- api_cost_usd_total (counter)
- cache_hits_total (counter)
- cache_misses_total (counter)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


class MetricsExporter:
    """Prometheus metrics exporter.
    
    Exports application metrics in Prometheus format.
    Metrics are lazily initialized to avoid import errors
    when prometheus_client is not installed.
    """

    def __init__(self) -> None:
        """Initialize metrics exporter."""
        self._initialized = False
        self._request_latency: Optional["Histogram"] = None
        self._requests_total: Optional["Counter"] = None
        self._tokens_total: Optional["Counter"] = None
        self._cost_total: Optional["Counter"] = None
        self._cache_hits: Optional["Counter"] = None
        self._cache_misses: Optional["Counter"] = None
        
    def _init_metrics(self) -> bool:
        """Initialize Prometheus metrics lazily.
        
        Returns:
            True if initialized successfully, False otherwise
        """
        if self._initialized:
            return True
            
        try:
            from prometheus_client import Counter, Histogram
            
            self._request_latency = Histogram(
                "api_request_latency_seconds",
                "API request latency in seconds",
                ["endpoint", "method"],
                buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
            )
            
            self._requests_total = Counter(
                "api_requests_total",
                "Total API requests",
                ["endpoint", "method", "status"],
            )
            
            self._tokens_total = Counter(
                "token_usage_total",
                "Total tokens used",
                ["model", "type"],  # type: input/output/cached
            )
            
            self._cost_total = Counter(
                "api_cost_usd_total",
                "Total API cost in USD",
                ["model"],
            )
            
            self._cache_hits = Counter(
                "cache_hits_total",
                "Total cache hits",
                ["cache_type"],
            )
            
            self._cache_misses = Counter(
                "cache_misses_total",
                "Total cache misses",
                ["cache_type"],
            )
            
            self._initialized = True
            logger.info("Prometheus metrics initialized")
            return True
            
        except ImportError:
            logger.warning("prometheus_client not installed, metrics disabled")
            return False
            
    def record_request(
        self,
        endpoint: str,
        method: str,
        latency_seconds: float,
        status_code: int,
    ) -> None:
        """Record API request metrics.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            latency_seconds: Request latency in seconds
            status_code: HTTP status code
        """
        if not self._init_metrics():
            return
            
        if self._request_latency:
            self._request_latency.labels(endpoint=endpoint, method=method).observe(
                latency_seconds
            )
            
        if self._requests_total:
            self._requests_total.labels(
                endpoint=endpoint, method=method, status=str(status_code)
            ).inc()
            
    def record_tokens(
        self,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> None:
        """Record token usage metrics.
        
        Args:
            model: Model name (e.g., 'gemini-pro')
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            cached_tokens: Cached tokens reused
        """
        if not self._init_metrics() or not self._tokens_total:
            return
            
        if input_tokens > 0:
            self._tokens_total.labels(model=model, type="input").inc(input_tokens)
        if output_tokens > 0:
            self._tokens_total.labels(model=model, type="output").inc(output_tokens)
        if cached_tokens > 0:
            self._tokens_total.labels(model=model, type="cached").inc(cached_tokens)
            
    def record_cost(self, model: str, cost_usd: float) -> None:
        """Record API cost metrics.
        
        Args:
            model: Model name
            cost_usd: Cost in USD
        """
        if not self._init_metrics() or not self._cost_total:
            return
            
        self._cost_total.labels(model=model).inc(cost_usd)
        
    def record_cache(self, cache_type: str, hit: bool) -> None:
        """Record cache hit/miss metrics.
        
        Args:
            cache_type: Type of cache (e.g., 'redis', 'memory')
            hit: True if cache hit, False if miss
        """
        if not self._init_metrics():
            return
            
        if hit and self._cache_hits:
            self._cache_hits.labels(cache_type=cache_type).inc()
        elif not hit and self._cache_misses:
            self._cache_misses.labels(cache_type=cache_type).inc()


# Global instance
_exporter = MetricsExporter()


def get_exporter() -> MetricsExporter:
    """Get global metrics exporter instance."""
    return _exporter
