# availability.py: production-ready functions for edge reliability analysis
import numpy as np
from math import comb
from scipy.stats import expon, weibull_min

def exp_reliability(t, lam):
    # lam: failure rate (1/time)
    return np.exp(-lam * np.asarray(t))

def weibull_reliability(t, eta, beta):
    # eta: scale, beta: shape
    return np.exp(- (np.asarray(t) / eta) ** beta)

def steady_state_availability(lam, mu):
    # lam: failure rate, mu: repair rate
    return mu / (lam + mu)

def k_of_n_reliability(t, k, n, reliability_func, *params):
    # reliability_func should accept (t, *params) and return R(t)
    R = reliability_func(t, *params)
    R = np.atleast_1d(R)
    out = np.zeros_like(R, dtype=float)
    for i, r in enumerate(R):
        # binomial sum for identical components
        s = 0.0
        for j in range(k, n+1):
            s += comb(n, j) * (r ** j) * ((1 - r) ** (n - j))
        out[i] = s
    return out if out.size > 1 else float(out)

# Example usage (integrate into CI pipelines or dashboards):
if __name__ == "__main__":
    # heterogeneous node example
    lam_node = 1.0 / (5 * 365 * 24)   # failures per hour for 5 years MTTF
    mu_node = 1.0 / 2.0               # repairs per hour for 2 hr MTTR
    A = steady_state_availability(lam_node, mu_node)
    print("steady-state availability:", A)
    # 2-of-3 quorum reliability at 24 hours with exponential model
    print("2-of-3 reliability at 24h:",
          k_of_n_reliability(24.0, 2, 3, exp_reliability, lam_node))