#!/usr/bin/env python3
# Query Prometheus, compute BI from CPU, mem, net, i/o, and tail latency.
import os
from prometheus_api_client import PrometheusConnect
import numpy as np

PROM = PrometheusConnect(url=os.environ.get("PROM_URL","http://prom:9090"), disable_ssl=True)
WEIGHTS = {"cpu":0.4, "gpu":0.3, "net":0.2, "io":0.1}  # tunable

def fetch_latest(metric, node):
    q = f'{metric}{{instance="{node}"}}'
    r = PROM.get_current_metric_value(q)
    return float(r[0]['value'][1]) if r else 0.0

def tail_latency(node):
    q = f'histogram_quantile(0.99, sum(rate(app_request_duration_seconds_bucket{{instance="{node}"}}[1m])) by (le))'
    r = PROM.custom_query(q)
    return float(r[0]['value'][1]) if r else 0.0

def compute_bi(node):
    cpu = fetch_latest('node_cpu_utilization', node)  # 0..1
    gpu = fetch_latest('nvidia_gpu_utilization', node)  # 0..1
    net = fetch_latest('node_network_utilization', node)  # 0..1
    io  = fetch_latest('node_io_utilization', node)  # 0..1
    tail = tail_latency(node)  # seconds
    tail_norm = min(1.0, tail / 0.5)  # normalize against SLO 500ms
    score = WEIGHTS['cpu']*cpu + WEIGHTS['gpu']*gpu + WEIGHTS['net']*net + WEIGHTS['io']*io
    # amplify score by tail latency presence
    return min(1.0, score * (1.0 + 2.0*tail_norm)), dict(cpu=cpu,gpu=gpu,net=net,io=io,tail=tail)

def rank_nodes(nodes):
    results = []
    for n in nodes:
        bi, metrics = compute_bi(n)
        results.append((n, bi, metrics))
    return sorted(results, key=lambda x: x[1], reverse=True)

if __name__ == "__main__":
    nodes = os.environ.get("EDGE_NODES","edge1:9100,edge2:9100").split(',')
    for n, bi, m in rank_nodes(nodes):
        print(f"{n}: BI={bi:.3f} cpu={m['cpu']:.2f} gpu={m['gpu']:.2f} net={m['net']:.2f} tail={m['tail']:.3f}s")