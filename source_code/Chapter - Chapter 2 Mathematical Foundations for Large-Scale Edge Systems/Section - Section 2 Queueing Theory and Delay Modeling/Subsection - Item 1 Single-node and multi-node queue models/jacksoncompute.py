#!/usr/bin/env python3
"""Compute M/M/1 metrics and Jackson-network sojourns.
Designed for deployment on edge-controller nodes (e.g., x86/ARM)."""

from typing import Sequence
import numpy as np

def mm1_metrics(lambda_rate: float, mu: float) -> dict:
    """Return utilization, mean queue wait, and sojourn time for M/M/1."""
    if lambda_rate <= 0 or mu <= 0:
        raise ValueError("Rates must be positive.")
    rho = lambda_rate / mu
    if rho >= 1.0:
        raise RuntimeError(f"Unstable: utilization {rho:.3f} >= 1")
    Wq = rho / (mu * (1 - rho))
    T = Wq + 1.0 / mu
    return {"rho": rho, "Wq": Wq, "T": T}

def jackson_network(lambda0: Sequence[float],
                    P: np.ndarray,
                    mu: Sequence[float]) -> dict:
    """
    Solve for effective arrival rates and M/M/1 sojourns.
    lambda0: external arrival vector (length N).
    P: NxN routing matrix, rows sum <= 1 (exit probability = 1-row_sum).
    mu: service rates for N nodes.
    """
    lambda0 = np.asarray(lambda0, dtype=float)
    mu = np.asarray(mu, dtype=float)
    N = len(lambda0)
    if P.shape != (N, N):
        raise ValueError("P must be NxN.")
    # Solve lambda = lambda0 + lambda P => (I - P^T) lambda^T = lambda0^T
    A = np.eye(N) - P.T
    try:
        lambda_eff = np.linalg.solve(A, lambda0)
    except np.linalg.LinAlgError:
        raise RuntimeError("Routing matrix leads to singular flow equations.")
    metrics = []
    for i in range(N):
        m = mm1_metrics(lambda_eff[i], mu[i])
        metrics.append(m)
    return {"lambda_eff": lambda_eff, "node_metrics": metrics}
# Example invocation in control plane:
# result = jackson_network([40.0, 0.0], np.array([[0.0,0.3],[0.0,0.0]]), [60.0,50.0])