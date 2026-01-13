#!/usr/bin/env python3
# Exposes CPU percent, memory percent, and network bytes/s for Prometheus.
import time
import psutil
from prometheus_client import start_http_server, Gauge

CPU_PCT = Gauge('edge_cpu_percent', 'CPU usage percent')
MEM_PCT = Gauge('edge_memory_percent', 'Memory usage percent')
NET_RX_BPS = Gauge('edge_net_rx_bytes_per_second', 'Network RX bytes/s', ['iface'])
NET_TX_BPS = Gauge('edge_net_tx_bytes_per_second', 'Network TX bytes/s', ['iface'])

def sample(interval=1.0):
    prev = psutil.net_io_counters(pernic=True)
    while True:
        cpu = psutil.cpu_percent(interval=None)  # non-blocking
        mem = psutil.virtual_memory().percent
        now = psutil.net_io_counters(pernic=True)
        CPU_PCT.set(cpu)
        MEM_PCT.set(mem)
        for iface, counters in now.items():
            p = prev.get(iface)
            if not p:
                prev[iface] = counters
                continue
            rx_bps = (counters.bytes_recv - p.bytes_recv) / interval
            tx_bps = (counters.bytes_sent - p.bytes_sent) / interval
            NET_RX_BPS.labels(iface=iface).set(rx_bps)
            NET_TX_BPS.labels(iface=iface).set(tx_bps)
            prev[iface] = counters
        time.sleep(interval)

if __name__ == '__main__':
    start_http_server(9100)  # Prometheus scrape endpoint
    sample(interval=1.0)