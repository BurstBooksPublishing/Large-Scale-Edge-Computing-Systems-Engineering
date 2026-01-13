# dp_edge.py -- DP utilities for edge aggregators (production-ready)
from typing import Sequence, Tuple
import numpy as np
import math
import logging

logger = logging.getLogger("dp_edge")
logging.basicConfig(level=logging.INFO)

def laplace_noise(scale: float, shape: Tuple[int, ...] = ()) -> np.ndarray:
    """Return Laplace noise with given scale b."""
    return np.random.laplace(loc=0.0, scale=scale, size=shape)

def gaussian_noise(sigma: float, shape: Tuple[int, ...] = ()) -> np.ndarray:
    """Return Gaussian noise with standard deviation sigma."""
    return np.random.normal(loc=0.0, scale=sigma, size=shape)

def laplace_mechanism(value: float, sensitivity: float, epsilon: float) -> float:
    b = sensitivity / epsilon
    return float(value + laplace_noise(b))

def gaussian_mechanism(value: float, sensitivity: float, epsilon: float,
                       delta: float) -> float:
    sigma = (sensitivity / epsilon) * math.sqrt(2 * math.log(1.25 / delta))
    return float(value + gaussian_noise(sigma))

def advanced_composition(eps: float, k: int, delta: float, delta_prime: float) -> float:
    """Advanced composition bound for k repeated (eps,delta)-DP mechanisms."""
    return math.sqrt(2 * k * math.log(1.0 / delta_prime)) * eps + \
           k * eps * (math.exp(eps) - 1)

def subsampling_amplification(eps: float, q: float) -> float:
    """Poisson subsampling amplification: effective epsilon after sampling."""
    return math.log(1.0 + q * (math.exp(eps) - 1.0))

def mse(original: Sequence[float], noisy: Sequence[float]) -> float:
    arr0 = np.asarray(original, dtype=float)
    arr1 = np.asarray(noisy, dtype=float)
    return float(np.mean((arr0 - arr1) ** 2))

# Example usage (to be called from orchestration code on gateway):
# noisy = laplace_mechanism(aggregate_count, sensitivity=1.0, epsilon=0.5)