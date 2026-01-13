#!/usr/bin/env python3
# Score edge nodes for placing data-processing tasks by locality and policy.
import os, requests, math
from kubernetes import client, config

PROM_URL = os.getenv("PROM_URL", "http://prometheus.monitoring:9090/api/v1/query")
K8S_CONFIG = os.getenv("KUBECONFIG")  # use in-cluster config if None

# load k8s client
if K8S_CONFIG:
    config.load_kube_config(K8S_CONFIG)
else:
    config.load_incluster_config()
v1 = client.CoreV1Api()

def query_prom(query):
    r = requests.get(PROM_URL, params={'query': query}, timeout=5)
    r.raise_for_status()
    return r.json()['data']['result']

def fetch_network_metrics(node_name):
    # expected to return bandwidth (bytes/s) and rtt (s)
    bw_q = f'node_network_bandwidth_bytes{{node="{node_name}"}}'
    rtt_q = f'probe_rtt_seconds{{instance="{node_name}"}}'
    try:
        bw = float(query_prom(bw_q)[0]['value'][1])
    except Exception:
        bw = 1e6  # fallback
    try:
        rtt = float(query_prom(rtt_q)[0]['value'][1])
    except Exception:
        rtt = 0.05
    return bw, rtt

def score_node(size_bytes, node, alpha=1.0, beta=0.5, gamma=0.1):
    labels = node.metadata.labels or {}
    # policy: local storage required label
    if labels.get('edge.local_storage') != 'true':
        return None
    bw, rtt = fetch_network_metrics(node.metadata.name)
    T = size_bytes / bw + rtt
    # simplistic compute and energy proxies from labels
    compute_ms = float(labels.get('capacity.compute_ms', '50'))
    energy = float(labels.get('power.per_op', '0.05'))
    cost = alpha * T + beta * (compute_ms/1000.0) + gamma * energy
    return cost, T, compute_ms

def rank_nodes(size_bytes):
    nodes = v1.list_node().items
    scored = []
    for n in nodes:
        s = score_node(size_bytes, n)
        if s is not None:
            scored.append((n.metadata.name,)+s)
    scored.sort(key=lambda x: x[1])  # sort by cost
    return scored

if __name__ == "__main__":
    import sys
    size = int(sys.argv[1]) if len(sys.argv) > 1 else 20_000_000
    for rec in rank_nodes(size):
        print(f"{rec[0]} cost={rec[1]:.4f} T={rec[2]:.3f}s comp_ms={rec[3]}")