"""Markov utilities: compute steady-state and simulate DTMC/CTMC."""
from typing import Tuple
import numpy as np
from scipy.linalg import eig, expm
import random

class MarkovChain:
    def __init__(self, P: np.ndarray):
        """DTMC: P is row-stochastic transition matrix."""
        assert P.ndim == 2 and P.shape[0] == P.shape[1]
        assert np.allclose(P.sum(axis=1), 1.0)
        self.P = P
        self.n = P.shape[0]

    def steady_state(self) -> np.ndarray:
        """Compute stationary distribution solving pi = pi P."""
        vals, vecs = eig(self.P.T)
        # index eigenvalue 1
        idx = np.argmin(np.abs(vals - 1.0))
        v = np.real(vecs[:, idx])
        pi = v / v.sum()
        return np.maximum(pi, 0.0)

    def simulate(self, start: int, steps: int) -> np.ndarray:
        """Simulate DTMC trajectory (returns state sequence)."""
        s = int(start)
        traj = np.empty(steps + 1, dtype=int)
        traj[0] = s
        for t in range(1, steps + 1):
            s = np.random.choice(self.n, p=self.P[s])
            traj[t] = s
        return traj

def simulate_ctmc_birth_death(N: int, lam: float, mu: float, tmax: float, seed: int=None) -> Tuple[np.ndarray, np.ndarray]:
    """Gillespie simulation of birth-death CTMC for node availability."""
    if seed is not None:
        random.seed(seed); np.random.seed(seed)
    t = 0.0
    k = N  # start with all nodes up
    times = [t]; states = [k]
    while t < tmax:
        birth = lam * (N - k)   # recoveries from down nodes
        death = mu * k         # failures from up nodes
        rate = birth + death
        if rate == 0:
            break
        dt = np.random.exponential(1.0 / rate)
        t += dt
        if random.random() < birth / rate:
            k = min(N, k + 1)
        else:
            k = max(0, k - 1)
        times.append(t); states.append(k)
    return np.array(times), np.array(states)