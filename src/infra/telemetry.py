"""Lightweight OpenTelemetry helpers with graceful degradation."""
# mypy: ignore-errors
# ruff: noqa: PERF203

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from typing_extensions import ParamSpec

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from opentelemetry import metrics, trace
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
except Exception as exc:  # pragma: no cover
    metrics = None
    trace = None
    OTLPMetricExporter = None
    OTLPSpanExporter = None
    MeterProvider = None
    PeriodicExportingMetricReader = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    logger.debug("OpenTelemetry not installed: %s", exc)

P = ParamSpec("P")
R = TypeVar("R")

_tracer = None
_meter = None


def init_telemetry(
    service_name: str = "gemini-qa-system",
    otlp_endpoint: str | None = None,
) -> None:
    """Initialize OpenTelemetry tracer and meter if available."""
    global _tracer, _meter
    if trace is None:
        logger.info("Telemetry disabled (opentelemetry not installed)")
        return

    endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("OTLP endpoint not configured, telemetry disabled")
        return

    resource = Resource.create({"service.name": service_name})

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)),
    )
    trace.set_tracer_provider(trace_provider)
    _tracer = trace.get_tracer(__name__)

    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter(__name__)
    logger.info("Telemetry initialized with endpoint: %s", endpoint)


def get_tracer():
    """Return tracer or a no-op tracer."""
    if trace is None:

        class _NoopSpan:
            def __enter__(self) -> _NoopSpan:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def set_attribute(self, *args: Any, **kwargs: Any) -> None:
                return None

            def record_exception(self, *args: Any, **kwargs: Any) -> None:
                return None

            def set_status(self, *args: Any, **kwargs: Any) -> None:
                return None

        class _NoopTracer:
            def start_as_current_span(self, *_: Any, **__: Any) -> _NoopSpan:
                return _NoopSpan()

        return _NoopTracer()
    return _tracer or trace.get_tracer(__name__)


def get_meter():
    """Return meter or a no-op meter."""
    if metrics is None:

        class _NoopCounter:
            def add(self, *_: Any, **__: Any) -> None:
                return None

        class _NoopMeter:
            def create_counter(self, *_: Any, **__: Any) -> _NoopCounter:
                return _NoopCounter()

        return _NoopMeter()
    return _meter or metrics.get_meter(__name__)


def _build_status(name: str, description: str | None = None) -> Any | None:
    """Safely construct a span status object if OpenTelemetry is available."""
    if trace is None:
        return None
    status_mod = getattr(trace, "status", None)
    status_cls = getattr(status_mod, "Status", None) if status_mod else None
    code_cls = getattr(status_mod, "StatusCode", None) if status_mod else None
    if not status_cls or not code_cls:
        return None
    code = getattr(code_cls, name, None)
    if code is None:
        return None
    try:
        return (
            status_cls(code, description)
            if description is not None
            else status_cls(code)
        )
    except Exception:
        return None


def traced(
    operation: str,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace sync functions."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = get_tracer()
            with tracer.start_as_current_span(operation) as span:
                if attributes:
                    for key, value in attributes.items():
                        try:
                            span.set_attribute(key, value)
                        except Exception:
                            continue
                try:
                    result = func(*args, **kwargs)
                    ok_status = _build_status("OK")
                    if ok_status and hasattr(span, "set_status"):
                        span.set_status(ok_status)
                    return result
                except Exception as exc:
                    try:
                        span.record_exception(exc)  # type: ignore[attr-defined]
                    finally:
                        error_status = _build_status("ERROR", str(exc))
                        if error_status and hasattr(span, "set_status"):
                            span.set_status(error_status)
                    raise

        return wrapper

    return decorator


def traced_async(
    operation: str,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace async functions."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            tracer = get_tracer()
            with tracer.start_as_current_span(operation) as span:
                if attributes:
                    for key, value in attributes.items():
                        try:
                            span.set_attribute(key, value)
                        except Exception:
                            continue
                try:
                    result = await func(*args, **kwargs)  # type: ignore[misc]
                    ok_status = _build_status("OK")
                    if ok_status and hasattr(span, "set_status"):
                        span.set_status(ok_status)
                    return result
                except Exception as exc:
                    try:
                        span.record_exception(exc)  # type: ignore[attr-defined]
                    finally:
                        error_status = _build_status("ERROR", str(exc))
                        if error_status and hasattr(span, "set_status"):
                            span.set_status(error_status)
                    raise

        return wrapper

    return decorator


__all__ = ["get_meter", "get_tracer", "init_telemetry", "traced", "traced_async"]
