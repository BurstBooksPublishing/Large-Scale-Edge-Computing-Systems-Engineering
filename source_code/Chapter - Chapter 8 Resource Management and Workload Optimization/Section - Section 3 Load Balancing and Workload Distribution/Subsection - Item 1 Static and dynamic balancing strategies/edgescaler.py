#!/usr/bin/env python3
# production-ready: uses kube client and Prometheus HTTP API
import time, math
from kubernetes import client, config
import requests

PROM_URL = "http://prometheus.monitoring.svc:9090/api/v1/query"
DEPLOY_NS = "edge-apps"
DEPLOY_NAME = "video-processor"
CPU_TARGET = 0.65  # target utilization
SMOOTH = 0.3       # exponential smoothing factor
MIN_REPLICAS, MAX_REPLICAS = 1, 20

config.load_incluster_config()  # runs inside cluster
apps = client.AppsV1Api()

def query_cpu(node_label):
    # query average CPU usage across pods with label
    q = f"avg(rate(container_cpu_usage_seconds_total{{pod=~\"{DEPLOY_NAME}.*\"}}[30s]))"
    r = requests.get(PROM_URL, params={"query": q}, timeout=3)
    return float(r.json()["data"]["result"][0]["value"][1])

def smooth(prev, sample):
    return prev*(1-SMOOTH) + sample*SMOOTH if prev is not None else sample

util_est = None
while True:
    try:
        sample = query_cpu(DEPLOY_NAME)
        util_est = smooth(util_est, sample)
        # compute desired replicas using target utilization
        current = apps.read_namespaced_deployment_scale(DEPLOY_NAME, DEPLOY_NS)
        cur_repl = current.spec.replicas
        desired = max(MIN_REPLICAS, min(MAX_REPLICAS, math.ceil(cur_repl * util_est / CPU_TARGET)))
        # hysteresis: change only if >10% diff
        if abs(desired - cur_repl) / max(1, cur_repl) > 0.10:
            current.spec.replicas = desired
            apps.replace_namespaced_deployment_scale(DEPLOY_NAME, DEPLOY_NS, current)
        time.sleep(10)
    except Exception:
        time.sleep(5)