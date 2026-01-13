import numpy as np
from scipy.sparse import diags
from scipy.sparse.linalg import spsolve

def birth_death_steady_state(N, lam, mu):
    """
    Compute steady-state probabilities for 0..N working nodes.
    N: total nodes (int)
    lam: failure rate per working node (float)
    mu: repair rate per failed node (float)
    Returns: numpy array pi of length N+1
    """
    size = N + 1
    # Off-diagonals: q_{k,k-1}=k*lam, q_{k,k+1}=(N-k)*mu
    lower = np.array([k * lam for k in range(1, size)])   # transitions to k-1
    upper = np.array([(N - k) * mu for k in range(size - 1)])  # transitions to k+1
    diag = -(np.concatenate(([0], lower)) + np.concatenate((upper, [0])))
    # Build sparse Q^T to solve pi^T Q = 0 with normalization
    offsets = [-1, 0, 1]
    data = np.vstack([lower, diag, upper])
    Q = diags(data, offsets, shape=(size, size), dtype=float).tocsc()
    # Replace one equation with normalization: sum pi = 1
    A = Q.transpose().toarray()
    A[-1, :] = 1.0
    b = np.zeros(size)
    b[-1] = 1.0
    pi = np.linalg.solve(A, b)  # small N typical on gateway devices
    return pi

# Example: 3-node cluster with lam=1e-4 per hour, mu=1 per hour
if __name__ == "__main__":
    pi = birth_death_steady_state(3, 1e-4, 1.0)
    availability = pi[2:].sum()  # quorum 2-of-3
    print(f"steady-state pi: {pi}, availability: {availability:.6f}")