from kubernetes import client, config
import heapq
# Load kubeconfig or in-cluster config
config.load_incluster_config()  # or config.load_kube_config()
v1 = client.CoreV1Api()
# Fetch nodes and metrics (assumes metrics-server or Prometheus adapter)
nodes = v1.list_node().items

def fetch_node_metrics(node_name):
    # Placeholder: integrate Prometheus or metrics API in production
    return {"rtt": 20.0, "cpu_used": 0.4, "mem_used": 0.5, "labels": {}}

def score_node(metrics, weights):
    # Lower score is better
    return weights['rtt']*metrics['rtt'] + weights['cpu']*metrics['cpu_used'] + weights['mem']*metrics['mem_used']

weights = {'rtt': 0.6, 'cpu': 0.3, 'mem': 0.1}
pq = []
for node in nodes:
    nm = fetch_node_metrics(node.metadata.name)
    s = score_node(nm, weights)
    heapq.heappush(pq, (s, node.metadata.name))

# Select best node and patch a Deployment/Pod with nodeSelector (idempotent)
best_score, best_node = heapq.heappop(pq)
# Example: patch deployment with nodeSelector (real code must handle RBAC, retries)
patch = {"spec": {"template": {"spec": {"nodeSelector": {"kubernetes.io/hostname": best_node}}}}}
apps = client.AppsV1Api()
apps.patch_namespaced_deployment(name="predictor", namespace="edge", body=patch)