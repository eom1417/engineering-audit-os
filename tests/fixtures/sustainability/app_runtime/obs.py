"""Observability primitives."""
from prometheus_client import Counter, Histogram, Gauge
import logging
import sentry_sdk
from opentelemetry import trace

requests_counter = Counter('requests_total', 'Total')
latency_histogram = Histogram('latency_seconds', 'Latency')
queue_gauge = Gauge('queue_size', 'Queue size')
logger = logging.getLogger('app')


def handler():
    logger.info("handling request")
    trace.tracer.start_span("op")
    requests_counter.inc()
    latency_histogram.observe(0.1)
    return {'ok': True}
