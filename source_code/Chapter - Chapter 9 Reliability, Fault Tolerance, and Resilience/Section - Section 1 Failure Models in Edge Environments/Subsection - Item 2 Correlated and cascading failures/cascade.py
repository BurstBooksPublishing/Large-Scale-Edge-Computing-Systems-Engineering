#!/usr/bin/env python3
# Production-ready script: compute spectral radius and simulate cascades.
from typing import Dict
import numpy as np
import networkx as nx

def build_matrix(G: nx.DiGraph) -> np.ndarray:
    nodes = list(G.nodes())
    idx = {n:i for i,n in enumerate(nodes)}
    A = np.zeros((len(nodes), len(nodes)), dtype=float)
    for u,v,data in G.edges(data=True):
        A[idx[v], idx[u]] = float(data.get('weight', 0.0))  # v depends on u
    return A, nodes

def spectral_radius(A: np.ndarray) -> float:
    evals = np.linalg.eigvals(A)
    return max(abs(evals))

def simulate_threshold(A: np.ndarray, theta: float, seed: np.ndarray, steps: int=10):
    x = seed.copy().astype(int)
    for _ in range(steps):
        load = A @ x
        x_next = (load >= theta).astype(int)
        if np.array_equal(x_next, x):
            break
        x = x_next
    return x

# Example usage (to be run in operator toolchain):
# G = nx.DiGraph()
# G.add_edge('gateway1','processorA', weight=0.3)  # processorA depends on gateway1
# ... build full dependency graph ...
# A, nodes = build_matrix(G)
# print("Spectral radius:", spectral_radius(A))
# final = simulate_threshold(A, theta=0.7, seed=np.array([1,0,0,...]))