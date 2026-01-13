#!/usr/bin/env python3
"""Compute stationary distribution for a CTMC generator Q."""
import numpy as np
from scipy.linalg import null_space

def build_Q(states, rates):
    # states: list of state names; rates: dict of (i,j)->rate
    n = len(states)
    Q = np.zeros((n, n))
    idx = {s:i for i,s in enumerate(states)}
    for (si,sj), r in rates.items():
        Q[idx[si], idx[sj]] = r
    for i in range(n):
        Q[i,i] = -np.sum(Q[i,:])
    return Q, idx

def stationary_pi(Q):
    # find left nullspace: solve pi Q = 0 subject to sum pi = 1
    ns = null_space(Q.T)  # null_space returns basis for nullspace of Q^T
    v = ns[:,0]
    pi = v / np.sum(v)
    pi = pi.real
    return pi

if __name__ == "__main__":
    states = ["U","D","X"]
    rates = {("U","D"): 0.001, ("U","X"): 0.0002,
             ("D","U"): 0.01,   ("X","U"): 0.005}
    Q, idx = build_Q(states, rates)
    pi = stationary_pi(Q)
    avail = pi[idx["U"]] + pi[idx["D"]]  # treated as operational if degraded allowed
    print("pi:", dict(zip(states, pi)))
    print("availability:", avail)