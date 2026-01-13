"""
Compute effective arrival rates and M/M/1 metrics for an open Jackson network.
Requires: numpy
"""
import numpy as np
from typing import Tuple

def jackson_metrics(P: np.ndarray, lam0: np.ndarray, mu: np.ndarray
                   ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    P: NxN routing probability matrix where P[i,j] = p_ij (row i -> col j).
    lam0: external arrival rates vector (Nx).
    mu: service rates vector (Nx).
    Returns: (lambda, rho, W) where W is mean waiting time per node.
    """
    N = P.shape[0]
    if P.shape != (N, N) or lam0.shape != (N,) or mu.shape != (N,):
        raise ValueError("Dimension mismatch")
    # Solve (I - P^T) lambda = lam0
    A = np.eye(N) - P.T
    if np.linalg.matrix_rank(A) < N:
        raise np.linalg.LinAlgError("Routing matrix leads to singular system")
    lam = np.linalg.solve(A, lam0)
    rho = lam / mu
    if np.any(rho >= 1.0):
        raise RuntimeError("Unstable node detected: rho >= 1")
    W = 1.0 / (mu - lam)  # mean waiting + service time for M/M/1
    return lam, rho, W

# Example usage:
if __name__ == "__main__":
    P = np.array([[0.0, 0.8, 0.2],
                  [0.0, 0.0, 1.0],
                  [0.0, 0.0, 0.0]])
    lam0 = np.array([5.0, 0.0, 0.0])
    mu  = np.array([20.0, 50.0, 200.0])
    lam, rho, W = jackson_metrics(P, lam0, mu)
    print("lambda:", lam, "rho:", rho, "sojourn W:", W)