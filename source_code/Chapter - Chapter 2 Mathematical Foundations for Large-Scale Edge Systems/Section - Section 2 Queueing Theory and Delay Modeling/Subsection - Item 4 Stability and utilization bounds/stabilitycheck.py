# Production-ready check for open Jackson-like networks.
import numpy as np

def check_stability(gamma, P, mu, eps=1e-9):
    # gamma: external arrival rates vector (n,)
    # P: routing matrix (n,n), rows sum to routing-out prob
    # mu: service rates vector (n,)
    n = len(gamma)
    I = np.eye(n)
    # Solve traffic equations: lambda = gamma (I-P)^{-1}
    try:
        inv = np.linalg.inv(I - P)
    except np.linalg.LinAlgError:
        raise ValueError("Routing matrix makes (I-P) singular; check closed loops or absorbing states.")
    lam = gamma @ inv
    rho = lam / mu
    stable = np.all(rho < 1 - eps)
    return {"lambda": lam, "rho": rho, "stable": bool(stable)}

# Example usage for an edge cluster (4 nodes)
gamma = np.array([25.0, 0.0, 0.0, 0.0])        # external arrival to node 0 (fps)
P = np.array([[0.0, 0.5, 0.5, 0.0],           # routing probabilities
              [0.0, 0.0, 0.0, 0.0],
              [0.0, 0.0, 0.0, 0.0],
              [0.0, 0.0, 0.0, 0.0]])
mu = np.array([50.0, 40.0, 40.0, 20.0])       # service rates (fps)
print(check_stability(gamma, P, mu))         # JSON-like result for orchestration systems