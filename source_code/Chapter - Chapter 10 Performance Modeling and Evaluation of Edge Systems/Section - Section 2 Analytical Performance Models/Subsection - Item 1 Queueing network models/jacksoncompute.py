import numpy as np

def jackson_network(lambda0, P, mu, v=None):
    """
    Compute steady-state arrival rates, utilizations, and mean response time.
    lambda0: external arrival vector (shape N,)
    P: routing matrix (shape N,N) where P[j,i]=p_ji
    mu: service rates vector (shape N,)
    v: optional visit vector; if None, v = (I-P^T)^{-1} lambda0 / sum(...) approximates visits
    Returns: dict with lambda, rho, R_node, R_net
    """
    lambda0 = np.asarray(lambda0, dtype=float)
    P = np.asarray(P, dtype=float)
    mu = np.asarray(mu, dtype=float)
    N = lambda0.size

    # Solve traffic equations: (I - P^T) lambda = lambda0
    A = np.eye(N) - P.T
    try:
        lam = np.linalg.solve(A, lambda0)
    except np.linalg.LinAlgError as e:
        raise ValueError("Routing matrix yields singular traffic system") from e

    # Utilization and stability check
    rho = lam / mu
    if np.any(rho >= 1.0):
        raise RuntimeError(f"Unstable node(s): rho >= 1 -> {rho}")

    # M/M/1 mean sojourn per node
    R_node = 1.0 / (mu - lam)

    # Visit ratios (if not provided), normalize so visits per job sum = 1
    if v is None:
        # Heuristic: visits proportional to lam (for open networks)
        v = lam / np.sum(lam) if np.sum(lam) > 0 else np.ones(N) / N

    R_net = np.dot(v, R_node)
    return {"lambda": lam, "rho": rho, "R_node": R_node, "R_net": float(R_net)}

# Example usage (gateway, jetson, cloud)
lambda0 = np.array([50.0, 0.0, 0.0])            # ext arrivals to node 0
P = np.array([[0.0, 0.0, 0.0],                 # from gateway to ...
              [0.7, 0.0, 0.0],                 # from jetson to gateway (0) etc.
              [0.3, 0.0, 0.0]])                # from cloud to gateway
# note: P[j,i] = p_ji (columns are destinations)
mu = np.array([200.0, 400.0, 2000.0])
print(jackson_network(lambda0, P, mu))