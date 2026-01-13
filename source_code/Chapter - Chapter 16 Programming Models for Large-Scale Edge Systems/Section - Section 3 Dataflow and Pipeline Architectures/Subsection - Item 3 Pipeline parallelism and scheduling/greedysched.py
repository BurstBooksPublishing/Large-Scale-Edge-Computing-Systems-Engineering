from typing import List, Dict, Tuple
# stage: (work_units) ; node: (compute_capacity, network_latency_to_other_nodes)
def place_pipeline(stages: List[float],
                   nodes: Dict[str, Tuple[float, Dict[str,float]]]) -> Dict[int,str]:
    # compute score = estimated processing time + network hop time to previous stage
    placement = {}
    prev_node = None
    for i, work in enumerate(stages):
        best_node, best_cost = None, float('inf')
        for node, (capacity, latencies) in nodes.items():
            proc = work / capacity                       # seconds per item estimate
            net = 0.0
            if prev_node is not None and prev_node != node:
                net = latencies.get(prev_node, latencies.get(node, 0.0))
            cost = proc + net
            if cost < best_cost:
                best_cost, best_node = cost, node
        placement[i] = best_node
        prev_node = best_node
    return placement

# Example usage: stages measured in CPU-ms, nodes capacities in CPU-ms per second
if __name__ == "__main__":
    stages = [5.0, 50.0, 20.0]  # ingest, cnn, aggregator
    nodes = {
        "cortex_m": (100.0, {"jetson": 0.02, "k3s":0.05}),
        "jetson":    (10000.0, {"cortex_m":0.02, "k3s":0.01}),
        "k3s":       (2000.0, {"jetson":0.01, "cortex_m":0.05}),
    }
    print(place_pipeline(stages, nodes))