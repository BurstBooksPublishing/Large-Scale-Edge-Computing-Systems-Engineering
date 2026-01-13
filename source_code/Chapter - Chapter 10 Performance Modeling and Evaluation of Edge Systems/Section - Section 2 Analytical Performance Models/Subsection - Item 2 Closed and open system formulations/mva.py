import numpy as np

def mva_single_server(N, V, S):
    """
    Compute throughput X(N), response R(N), and per-center queue lengths L_i(N).
    N : int, population
    V : array_like, visit ratios length M
    S : array_like, service times length M
    Returns (X, R, L) where L is array length M.
    """
    V = np.asarray(V, dtype=float)
    S = np.asarray(S, dtype=float)
    M = len(V)
    L = np.zeros((N+1, M), dtype=float)  # L[n,i]
    for n in range(1, N+1):
        # per-center residence times using previous queue lengths
        R_i = S * (1.0 + L[n-1])
        R_total = np.dot(V, R_i)
        X = n / R_total  # throughput at population n
        L[n] = X * V * R_i  # Little's law per center
    # final stats
    R_final = np.dot(V, S * (1.0 + L[N-1]))
    X_final = N / R_final
    return X_final, R_final, L[N]

# Example usage:
# N=8 cameras, two centers: capture (S=0.005s, V=1), inference (S=0.1s, V=1)
# X, R, L = mva_single_server(8, [1,1], [0.005, 0.1])