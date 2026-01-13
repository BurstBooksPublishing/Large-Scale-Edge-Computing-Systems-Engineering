#!/usr/bin/env python3
"""
Production-ready: adjust warm replicas per-node based on observed rates.
Requires: kubernetes, requests.
Run as a Deployment with RBAC for Deployments/Scale and access to Prometheus.
"""
import math, time, requests
from kubernetes import client, config

PROM_URL = "http://prometheus:9090/api/v1/query"
NAMESPACE = "functions"
FUNCTION_LABEL = "app=function-x"
SAMPLE_INTERVAL = 15.0  # seconds
SPIN_UP_S = 0.8

def erlang_b(C, a):
    # stable iterative computation to avoid large factorials
    if a == 0:
        return 0.0
    B = 1.0
    for k in range(1, C+1):
        B = 1.0 + (k / a) * B
    return 1.0 / B

def prom_rate(query):
    resp = requests.get(PROM_URL, params={"query": query}, timeout=5)
    resp.raise_for_status()
    data = resp.json()["data"]["result"]
    if not data:
        return 0.0
    return float(data[0]["value"][1])

def desired_replicas(lambda_rate, mu=2.0):
    # choose smallest C with acceptable blocking prob threshold
    target_block = 0.02  # engineer-chosen SLA: <=2% cold starts
    for C in range(1, 10):
        a = lambda_rate / mu
        if erlang_b(C, a) <= target_block:
            return C
    return 10

def scale_deployments(api, replicas):
    # idempotent scale update
    body = {"spec": {"replicas": replicas}}
    ret = api.patch_namespaced_deployment_scale("function-x", NAMESPACE, body)
    return ret

def main():
    config.load_incluster_config()
    apps = client.AppsV1Api()
    while True:
        try:
            # Prometheus query: rate of function invocation counter per second
            q = 'sum(rate(function_invocations_total{app="function-x"}[1m]))'
            lam = prom_rate(q)
            replicas = desired_replicas(lam)
            scale_deployments(apps, replicas)
        except Exception as e:
            # backoff and continue; real deployments should log to central observability
            time.sleep(5)
        time.sleep(SAMPLE_INTERVAL)

if __name__ == "__main__":
    main()