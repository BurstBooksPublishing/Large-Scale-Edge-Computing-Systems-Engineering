#!/usr/bin/env python3
"""
Topology abstraction builder.
Input CSV columns: src,dst,latency_ms,bandwidth_mbps,loss
Outputs: JSON topology, Laplacian eigenvalues, cluster assignment.
"""
from typing import Dict, Any
import csv, json
import networkx as nx
import numpy as np
from scipy.sparse import csgraph
from scipy.linalg import eigh

def load_measurements(path: str) -> nx.DiGraph:
    g = nx.DiGraph()
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            u, v = r['src'], r['dst']
            lat = float(r['latency_ms']); bw = float(r['bandwidth_mbps'])
            loss = float(r.get('loss', 0.0))
            # composite weight: lower is better for spectral use
            weight = lat + 1000.0/max(1.0, bw) + 1000.0*loss
            g.add_edge(u, v, latency=lat, bandwidth=bw, loss=loss, weight=weight)
            # ensure nodes exist
            if u not in g: g.add_node(u)
            if v not in g: g.add_node(v)
    return g

def symmetric_weight_matrix(g: nx.DiGraph) -> np.ndarray:
    nodes = list(g.nodes())
    n = len(nodes)
    W = np.zeros((n, n))
    idx = {node:i for i,node in enumerate(nodes)}
    for u,v,data in g.edges(data=True):
        i,j = idx[u], idx[v]
        w = data['weight']
        # symmetrize by min of two directions if present
        W[i,j] = min(W[i,j] if W[i,j]>0 else np.inf, w) if W[i,j] else w
        W[j,i] = W[i,j]
    W[np.isinf(W)] = 0.0
    return W, nodes

def spectral_partition(W: np.ndarray, k: int=2) -> np.ndarray:
    L = np.diag(W.sum(axis=1)) - W  # Laplacian
    # compute smallest k eigenvectors (use eigh on dense L for small graphs)
    vals, vecs = eigh(L)
    # use eigenvectors 1..k-1 (skip the zero eigenvalue)
    features = vecs[:, 1:k]
    # k-means in spectral space (simple deterministic split using sign of first vec)
    if k==2:
        labels = (features[:,0] > 0).astype(int)
    else:
        # fallback: k-means using numpy (production code: use sklearn)
        from sklearn.cluster import KMeans
        labels = KMeans(n_clusters=k, random_state=0).fit_predict(features)
    return labels, np.linalg.eigvals(L)

def build_topology(path: str, k: int=2) -> Dict[str, Any]:
    g = load_measurements(path)
    W, nodes = symmetric_weight_matrix(g)
    labels, eigs = spectral_partition(W, k=k)
    topo = {'nodes': [], 'edges': [], 'eigenvalues': eigs.real.tolist()}
    for i,node in enumerate(nodes):
        topo['nodes'].append({'id': node, 'cluster': int(labels[i])})
    for u,v,data in g.edges(data=True):
        topo['edges'].append({'src':u,'dst':v,'latency':data['latency'],
                              'bandwidth':data['bandwidth'],'loss':data['loss']})
    return topo

if __name__ == '__main__':
    import sys
    topo = build_topology(sys.argv[1], k=2)
    print(json.dumps(topo, indent=2))  # integrate with orchestration via STDOUT