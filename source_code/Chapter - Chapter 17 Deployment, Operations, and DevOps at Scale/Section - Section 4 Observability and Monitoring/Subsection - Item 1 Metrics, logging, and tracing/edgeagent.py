#!/usr/bin/env python3
# Minimal production-ready edge agent for Linux-based edge nodes.
import time, socket, signal, sys
from prometheus_client import Gauge, start_http_server
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import \
    OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configuration (override via env or config file in production)
PROM_PORT = 9100
OTLP_ENDPOINT = "collector.local:4317"
NODE_ID = socket.gethostname()

# Prometheus metrics
cpu_gauge = Gauge("edge_cpu_percent", "CPU usage percent", ['node'])
mem_gauge = Gauge("edge_mem_mb", "Memory usage megabytes", ['node'])

# OpenTelemetry tracing with batching processor for network efficiency
resource = Resource(attributes={"service.name": "edge-agent", "host.name": NODE_ID})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=False)  # use TLS in prod
span_processor = BatchSpanProcessor(otlp_exporter, max_export_batch_size=512,
                                    schedule_delay_millis=2000, max_queue_size=2048)
tracer_provider.add_span_processor(span_processor)
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)

def sample_system_metrics():
    # Replace with psutil or platform-specific calls; keep light-weight.
    import os
    cpu = os.getloadavg()[0]  # coarse proxy
    mem = int((os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')) / (1024*1024))
    return cpu, mem

def graceful_exit(signum, frame):
    span_processor.shutdown()  # flush spans
    sys.exit(0)

signal.signal(signal.SIGTERM, graceful_exit)
signal.signal(signal.SIGINT, graceful_exit)

if __name__ == "__main__":
    start_http_server(PROM_PORT)  # exposes /metrics for Prometheus
    while True:
        cpu, mem = sample_system_metrics()
        cpu_gauge.labels(node=NODE_ID).set(cpu)
        mem_gauge.labels(node=NODE_ID).set(mem)
        # Example traced operation
        with tracer.start_as_current_span("sensor_read") as span:
            span.set_attribute("node.id", NODE_ID)
            time.sleep(1.0)  # replace with I/O-bound sensor read
        time.sleep(1.0)