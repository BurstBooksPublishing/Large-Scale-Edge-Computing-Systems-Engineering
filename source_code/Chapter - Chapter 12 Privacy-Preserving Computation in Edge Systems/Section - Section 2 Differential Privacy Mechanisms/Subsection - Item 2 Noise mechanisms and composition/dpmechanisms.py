import os
import math
import numpy as np

# Secure RNG seeded from OS entropy for deterministic replay protection.
_seed = int.from_bytes(os.urandom(8), "big")
_rng = np.random.default_rng(_seed)

def laplace_noise(scale: float, shape=()):
    """Draw Laplace noise with scale b; uses NumPy's generator."""
    u = _rng.random(shape) - 0.5
    return -scale * np.sign(u) * np.log1p(-2 * np.abs(u))

def gaussian_noise(sigma: float, shape=()):
    """Draw Gaussian noise using secure RNG."""
    return _rng.normal(loc=0.0, scale=sigma, size=shape)

def laplace_mechanism(value, sensitivity, epsilon):
    b = sensitivity / epsilon
    return value + laplace_noise(b)

def gaussian_mechanism(value, sensitivity, epsilon, delta):
    # Use the standard sufficient sigma bound from DP theory.
    sigma = (sensitivity / epsilon) * math.sqrt(2.0 * math.log(1.25 / delta))
    return value + gaussian_noise(sigma)

# Simple RDP accountant for Gaussian: RDP orders add across rounds.
def gaussian_rdp_sigma_to_alpha_rdp(sigma: float, alpha: float):
    """RDP epsilon_alpha for Gaussian noise at order alpha (>1)."""
    return alpha / (2 * sigma * sigma)

def compose_rdp(rdps):
    """Sum RDP epsilons across composed mechanisms (per-order)."""
    return sum(rdps)

# Example: compute sigma for 10 rounds, compose RDP and convert to (eps,delta).
def rdp_compose_to_eps(rdps, delta, alpha):
    """Convert composed RDP epsilon_alpha to (eps,delta)-DP via bound."""
    eps_alpha = compose_rdp(rdps)
    # Conversion example: eps = eps_alpha + log(1/delta)/(alpha-1)
    return eps_alpha + math.log(1.0 / delta) / (alpha - 1.0)