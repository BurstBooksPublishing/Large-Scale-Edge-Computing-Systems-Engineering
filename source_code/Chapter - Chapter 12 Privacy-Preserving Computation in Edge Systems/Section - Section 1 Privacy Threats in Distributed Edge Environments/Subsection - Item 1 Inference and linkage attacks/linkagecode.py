#!/usr/bin/env python3
# Compact, dependency-light implementation suitable for edge nodes.
import numpy as np
from typing import Iterable, Dict

def bayes_update(prior: np.ndarray, likelihood: np.ndarray) -> np.ndarray:
    """One-step Bayesian posterior update (vectorized)."""
    unnorm = prior * likelihood
    s = unnorm.sum()
    if s == 0:
        # Numerical safety: return prior (no info) to avoid collapse
        return prior
    return unnorm / s

def streaming_posteriors(priors: np.ndarray,
                         likelihood_stream: Iterable[np.ndarray],
                         threshold: float = 0.9) -> Dict[int,int]:
    """
    Update posteriors for candidate set sequentially.
    Returns mapping candidate_index -> first time index crossing threshold.
    """
    post = priors.copy()
    disclosures = {}
    for t, lik in enumerate(likelihood_stream):
        post = bayes_update(post, lik)
        # check for cross-threshold disclosures
        crossed = np.where((post >= threshold) & (np.arange(post.size)[:,None] >= 0))[0]
        for idx in crossed:
            if idx not in disclosures:
                disclosures[idx] = t
        # optional: early exit if all disclosed or max t reached
    return disclosures

def empirical_mutual_info(X: np.ndarray, Y: np.ndarray, bins=16) -> float:
    """Estimate I(X;Y) using histogram-based estimator (low-memory)."""
    # joint histogram
    jh, _, _ = np.histogram2d(X.ravel(), Y.ravel(), bins=bins)
    pxy = jh / jh.sum()
    px = pxy.sum(axis=1, keepdims=True)
    py = pxy.sum(axis=0, keepdims=True)
    nz = pxy > 0
    mi = (pxy[nz] * np.log(pxy[nz] / (px[nz.sum(axis=1)>0] * py[0, nz.sum(axis=0)>0])))
    # safe fallback if numerical shapes are degenerate
    return float(np.nansum(mi))
# Example usage on edge: compute posterior updates from streamed aggregated counts.