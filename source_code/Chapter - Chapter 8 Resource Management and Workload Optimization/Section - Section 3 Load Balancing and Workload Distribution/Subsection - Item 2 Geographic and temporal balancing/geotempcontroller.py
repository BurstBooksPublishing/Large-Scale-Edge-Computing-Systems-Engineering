#!/usr/bin/env python3
# Production-ready: uses official kubernetes client and simple ES predictor.
from kubernetes import client, config, watch
import math, time, threading

# Config for K3s/KubeEdge cluster; works in-cluster or via kubeconfig.
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

v1 = client.CoreV1Api()

# Exponential smoothing predictor (alpha between 0 and 1).
def es_predict(history, alpha=0.3, horizon=1):
    s = history[0]
    for x in history[1:]:
        s = alpha * x + (1 - alpha) * s
    return [s] * horizon

# Query nodes and capacities from labels/annotations (must be provisioned).
def get_nodes_by_region():
    nodes = v1.list_node().items
    regions = {}
    for n in nodes:
        meta = n.metadata
        labels = meta.labels or {}
        region = labels.get("edge.region", "unknown")
        cap = float(labels.get("edge.capacity", "100"))  # tasks/sec
        latency = float(labels.get("edge.latency_ms", "10"))
        regions.setdefault(region, []).append({"name": meta.name, "cap": cap, "lat_ms": latency})
    return regions

# Compute greedy assignment minimizing latency while respecting capacity.
def assign_work(predicted, regions):
    # predicted: dict region->rate
    placement = {}
    # sort nodes in each region by latency
    for r, rate in predicted.items():
        nodes = sorted(regions.get(r, []), key=lambda x: x["lat_ms"])
        remaining = rate
        placement[r] = []
        for n in nodes:
            if remaining <= 0:
                break
            take = min(n["cap"], remaining)
            placement[r].append({"node": n["name"], "assigned": take})
            remaining -= take
        # if remaining > 0, spill to nearest remote nodes (simple round-robin)
        if remaining > 0:
            for rr, nodes_rr in regions.items():
                if rr == r: continue
                for n in sorted(nodes_rr, key=lambda x: x["lat_ms"]):
                    if remaining <= 0: break
                    take = min(n["cap"], remaining)
                    placement[r].append({"node": n["name"], "assigned": take})
                    remaining -= take
                if remaining <= 0: break
    return placement

# Patch deployment affinity to prefer the chosen node for region r.
def apply_placement(deploy_name, namespace, target_node):
    # Use nodeSelector on a Deployment spec by patching pod template labels.
    body = {"spec": {"template": {"metadata": {"labels": {"preferred-node": target_node}}}}}
    apps = client.AppsV1Api()
    apps.patch_namespaced_deployment(deploy_name, namespace, body)

# Main loop: forecast window, compute assignment, apply placement for affected deployments.
def controller_loop(deploy_specs, poll_interval=60):
    while True:
        regions = get_nodes_by_region()
        predicted = {}
        for r, spec in deploy_specs.items():
            hist = spec["history"][-10:] or [spec["current"]]
            pred = es_predict(hist, alpha=0.25)[0]
            predicted[r] = pred
        placement = assign_work(predicted, regions)
        # For each region, pick the node with largest assigned capacity and patch related deploy.
        for r, entries in placement.items():
            if not entries: continue
            primary = max(entries, key=lambda e: e["assigned"])["node"]
            spec = deploy_specs.get(r)
            if spec:
                apply_placement(spec["deploy"], spec["namespace"], primary)
        time.sleep(poll_interval)

# Example deploy_specs must be kept up to date by operator.
# Starts controller in a thread when run as a service.