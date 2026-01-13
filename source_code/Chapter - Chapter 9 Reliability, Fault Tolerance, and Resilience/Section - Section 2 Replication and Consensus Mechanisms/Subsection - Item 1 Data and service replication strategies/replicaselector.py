import requests
from typing import List, Dict, Tuple

# Query node metrics endpoint; metric JSON must expose 'rtt_ms', 'fail_prob', 'free_storage_mb'
def get_node_metrics(node_url: str) -> Dict:
    # short timeout to avoid controller stalls
    resp = requests.get(f"{node_url}/metrics/json", timeout=1.0)
    resp.raise_for_status()
    return resp.json()

# Select r replicas minimizing max RTT while satisfying durability and storage
def select_replicas(node_urls: List[str], r: int, eps: float, required_storage_mb: int
                   ) -> List[str]:
    nodes = []
    for u in node_urls:
        m = get_node_metrics(u)
        nodes.append((u, float(m['rtt_ms']), float(m['fail_prob']), int(m['free_storage_mb'])))
    # Sort by RTT ascending for greedy selection
    nodes.sort(key=lambda x: x[1])
    selected = []
    total_storage = 0
    # Greedy pick until r reached and durability satisfied
    for u, rtt, p, storage in nodes:
        selected.append((u, rtt, p, storage))
        total_storage += storage
        if len(selected) >= r:
            # independent-failure model: product of p_i
            p_loss = 1.0
            for _, _, p_i, _ in selected:
                p_loss *= p_i
            if p_loss <= eps and total_storage >= required_storage_mb:
                return [u for u, *_ in selected]
    raise RuntimeError("No feasible replica set found under constraints")

# Example controller call:
# replicas = select_replicas(edge_node_urls, r=3, eps=1e-6, required_storage_mb=1024)