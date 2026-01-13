#!/usr/bin/env python3
# Compute graph metrics and simulate failures; outputs JSON summary.
import argparse, json, logging
import networkx as nx
import numpy as np
from scipy.sparse.linalg import eigsh

def algebraic_connectivity(G):
    L = nx.laplacian_matrix(G).astype(float)
    # compute two smallest eigenvalues; ignore zero eigenvalue
    vals, _ = eigsh(L, k=2, which='SM')
    return float(np.sort(vals)[1])

def simulate_failures(G, p_removal, mode='edge', trials=50):
    rng = np.random.default_rng()
    results = []
    edges = list(G.edges())
    nodes = list(G.nodes())
    for _ in range(trials):
        H = G.copy()
        if mode == 'edge':
            to_remove = rng.choice(len(edges), size=int(p_removal*len(edges)), replace=False)
            H.remove_edges_from([edges[i] for i in to_remove])
        else:
            to_remove = rng.choice(len(nodes), size=int(p_removal*len(nodes)), replace=False)
            H.remove_nodes_from([nodes[i] for i in to_remove])
        comps = [len(c) for c in nx.connected_components(H)]
        largest = max(comps) if comps else 0
        diam = nx.diameter(H.subgraph(max(nx.connected_components(H), key=len))) if largest>0 else None
        results.append({'largest_cc': largest, 'diameter': diam})
    return results

def main():
    p = argparse.ArgumentParser()
    p.add_argument('graph', help='input graph edge list (CSV or edgelist)')
    p.add_argument('--fail-rate', type=float, default=0.1)
    p.add_argument('--mode', choices=('edge','node'), default='edge')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO)
    G = nx.read_edgelist(args.graph)
    metrics = {
        'num_nodes': G.number_of_nodes(),
        'num_edges': G.number_of_edges(),
        'vertex_connectivity': nx.node_connectivity(G),
        'edge_connectivity': nx.edge_connectivity(G),
        'diameter': nx.diameter(G),
        'algebraic_connectivity': algebraic_connectivity(G)
    }
    sim = simulate_failures(G, args.fail_rate, mode=args.mode)
    metrics['failure_sim'] = sim
    print(json.dumps(metrics, indent=2))

if __name__ == '__main__':
    main()