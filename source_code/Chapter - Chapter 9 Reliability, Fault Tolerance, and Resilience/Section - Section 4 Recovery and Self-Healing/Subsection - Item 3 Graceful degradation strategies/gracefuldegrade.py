#!/usr/bin/env python3
# Production-ready: uses Prometheus HTTP API and Kubernetes python-client.
import time, os, requests
from kubernetes import client, config

PROM_URL = os.getenv("PROM_URL", "http://prometheus:9090")
NAMESPACE = os.getenv("NAMESPACE", "default")
CPU_THRESH = float(os.getenv("CPU_THRESH", "0.85"))  # fraction of CPU
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10"))
LABEL = "degrade=lowprio"

# Load kubeconfig (in-cluster or local)
try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()
apps = client.AppsV1Api()
core = client.CoreV1Api()

def query_prom(query):
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": query}, timeout=5)
    r.raise_for_status()
    return r.json()

def current_node_cpu_frac():
    # average CPU usage across nodes as fraction of allocatable
    q = 'sum(node_cpu_seconds_total{mode!="idle"}) / sum(machine_cpu_cores)'
    resp = query_prom(q)
    val = float(resp["data"]["result"][0]["value"][1]) if resp["data"]["result"] else 0.0
    return val

def scale_deployments(replicas):
    deps = apps.list_namespaced_deployment(NAMESPACE, label_selector=LABEL)
    for d in deps.items:
        name = d.metadata.name
        body = {'spec': {'replicas': replicas}}
        apps.patch_namespaced_deployment_scale(name, NAMESPACE, body)  # idempotent

def toggle_model_fidelity(low=True):
    # atomically patch a ConfigMap used by pods for model selection
    name = "model-config"
    cm = core.read_namespaced_config_map(name, NAMESPACE)
    cm.data["fidelity"] = "low" if low else "high"
    core.patch_namespaced_config_map(name, NAMESPACE, cm)

if __name__ == "__main__":
    degraded = False
    while True:
        try:
            cpu_frac = current_node_cpu_frac()
            if cpu_frac > CPU_THRESH and not degraded:
                scale_deployments(0)         # reduce low-priority work
                toggle_model_fidelity(low=True)
                degraded = True
            elif cpu_frac < CPU_THRESH*0.8 and degraded:
                scale_deployments(2)         # restore conservative replicas
                toggle_model_fidelity(low=False)
                degraded = False
        except Exception as e:
            # robust logging and backoff in production
            print("controller error:", e)
        time.sleep(CHECK_INTERVAL)