# production-ready asyncio service for mobility-driven reallocation
import asyncio
from kubernetes import client, config
import math, time

# initialize K8s client (in-cluster or kubeconfig)
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()
api = client.AppsV1Api()

# simple exponential smoothing predictor for target node id
def predict_node(history, alpha=0.6):
    # history: list of (timestamp, node_id) recent attachments
    if not history:
        return None
    weights = {}
    s = 1.0
    for _, nid in reversed(history):
        weights[nid] = weights.get(nid, 0.0) + s
        s *= (1.0 - alpha)
    return max(weights.items(), key=lambda x: x[1])[0]

def migration_time_bytes(state_bytes, bandwidth_bps, overhead=0.1):
    # return seconds; overhead accounts for protocol/RTT inefficiency
    return state_bytes / (bandwidth_bps * (1.0 - overhead))

async def relocate_deployment(namespace, name, target_node, timeout=60):
    # patch deployment nodeSelector to target_node; handle rollout
    body = {"spec": {"template": {"spec": {"nodeSelector": {"edge-node": target_node}}}}}
    api.patch_namespaced_deployment(name, namespace, body)
    # wait for rollout completion with timeout
    end = time.time() + timeout
    while time.time() < end:
        dep = api.read_namespaced_deployment(name, namespace)
        if dep.status.updated_replicas == dep.status.replicas \
           and dep.status.available_replicas == dep.status.replicas:
            return True
        await asyncio.sleep(1.0)
    return False

async def control_loop(state_size_bytes, bandwidth_provider, attachment_history,
                       namespace, deployment_name, beta=1.0):
    # bandwidth_provider(): async function returning estimated bps to target
    while True:
        target = predict_node(attachment_history)
        if target is None:
            await asyncio.sleep(0.5); continue
        bps = await bandwidth_provider(target)
        t_mig = migration_time_bytes(state_size_bytes, bps)
        # simple latency estimates (replace with measurements)
        l_current = 0.05  # s
        l_target = 0.02   # s
        # predicted useful lifetime (seconds) heuristic
        tau = 30.0
        benefit = max(0.0, (l_current - l_target) * tau)
        cost = t_mig + beta * (state_size_bytes / 1e6)  # beta scales MB cost
        if benefit > cost:
            success = await relocate_deployment(namespace, deployment_name, target)
            # record outcome, adjust beta or predictor if migration fails
        await asyncio.sleep(1.0)