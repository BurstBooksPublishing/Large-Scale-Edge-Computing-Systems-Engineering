import numpy as np

def covariance_intersection(means, covs, weights=None, eps=1e-9):
    """
    Fuse N Gaussian estimates via iterative CI.
    means: list of (d,) numpy arrays
    covs: list of (d,d) numpy arrays
    weights: optional list of omega values for pairwise CI [0,1]
    Returns fused (mu, P)
    """
    assert len(means) == len(covs) >= 1
    mu = means[0].copy()
    P = covs[0].copy()
    for i in range(1, len(means)):
        mu_i = means[i]
        P_i = covs[i]
        # select omega if provided, else optimize simple grid (cheap)
        if weights is not None:
            omega = weights[min(i-1, len(weights)-1)]
        else:
            # grid search for omega minimizing trace
            candidates = np.linspace(0.0, 1.0, 21)
            best_tr = np.inf
            best_omega = 0.5
            for w in candidates:
                try:
                    S = w*np.linalg.inv(P) + (1-w)*np.linalg.inv(P_i)
                except np.linalg.LinAlgError:
                    continue
                P_candidate = np.linalg.inv(S)
                if np.trace(P_candidate) < best_tr:
                    best_tr = np.trace(P_candidate)
                    best_omega = w
            omega = best_omega
        # compute fused information matrix
        S = omega*np.linalg.inv(P) + (1-omega)*np.linalg.inv(P_i)
        # numerically robust inversion
        try:
            P = np.linalg.inv(S)
        except np.linalg.LinAlgError:
            P = np.linalg.pinv(S)
        mu = P.dot(omega*np.linalg.inv(P).dot(mu) + (1-omega)*np.linalg.inv(P_i).dot(mu_i))
    # ensure symmetry and positive definiteness approximated
    P = 0.5*(P + P.T) + eps*np.eye(P.shape[0])
    return mu, P

# Example usage: fuse two 3D position estimates on RSU
# mu1 = np.array([10.0, 2.0, 0.0]); P1 = np.diag([1.0,0.8,0.5])
# mu2 = np.array([9.5,2.1,0.1]); P2 = np.diag([0.6,0.9,0.7])
# fused_mu, fused_P = covariance_intersection([mu1,mu2],[P1,P2])