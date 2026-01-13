#!/usr/bin/env python3
# Minimal dependencies: prometheus_api_client, kubernetes
from prometheus_api_client import PrometheusConnect
from kubernetes import client, config
import time, math, statistics

PROM_URL = "http://prometheus.local:9090"
QUERY_CPU = 'avg_over_time(node_cpu_seconds_total{instance="%s",mode!="idle"}[5s])'
SAMPLE_INTERVAL = 5.0
ALPHA = 0.2
THRESHOLD = 0.85  # normalized score threshold

# initialize clients
prom = PrometheusConnect(url=PROM_URL, disable_ssl=True)
config.load_kube_config()  # works with K3s or cloud kubeconfig
apps = client.AppsV1Api()

# keep EWMA state in memory
ewma = {}  # {instance: smoothed_value}

def fetch_cpu(instance):
    q = QUERY_CPU % instance
    res = prom.custom_query(q)
    if not res: return None
    return float(res[0]['value'][1])

def hotspot_score(instance):
    cpu = fetch_cpu(instance)
    if cpu is None: return 0.0
    s = ewma.get(instance, cpu)
    s = (1-ALPHA)*s + ALPHA*cpu
    ewma[instance] = s
    # normalize by a conservative capacity estimate (e.g., 1.0 cores per metric)
    return s  # caller must normalize for multi-core devices

def mitigate_scale(namespace, deploy_name, scale_to):
    # scale deployment replicas using patch call (safe, idempotent)
    body = {'spec': {'replicas': int(scale_to)}}
    apps.patch_namespaced_deployment_scale(deploy_name, namespace, body)

def main_loop(instances, namespace, deploy_name, max_replicas):
    while True:
        for inst in instances:
            score = hotspot_score(inst)
            norm = min(1.0, score)  # normalize for 1.0 == full capacity
            if norm > THRESHOLD:
                # simple mitigation: scale up if possible
                cur = apps.read_namespaced_deployment_scale(deploy_name, namespace)
                cur_rep = cur.spec.replicas or 1
                if cur_rep < max_replicas:
                    mitigate_scale(namespace, deploy_name, cur_rep+1)
        time.sleep(SAMPLE_INTERVAL)

if __name__ == "__main__":
    # run for a set of edge instances and a deployment handling their load
    instances = ["edge1.local:9100", "edge2.local:9100"]
    main_loop(instances, "factory", "video-inference", max_replicas=5)