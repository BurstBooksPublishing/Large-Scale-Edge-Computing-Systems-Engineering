#!/usr/bin/env python3
# Production helper: compute minimal servers to meet tail SLO and validate by sampling.

import math
import random
import statistics
from typing import Callable, List

def erlang_c(c: int, lam: float, mu: float) -> float:
    # Compute Erlang C probability of queueing.
    rho_k = lam / mu
    sum_terms = sum((rho_k**k) / math.factorial(k) for k in range(c))
    last = (rho_k**c) / math.factorial(c) * (c / (c - rho_k))
    return last / (sum_terms + last)

def tail_wait_prob(c: int, lam: float, mu: float, t: float) -> float:
    # P(wait > t) for M/M/c
    ec = erlang_c(c, lam, mu)
    return ec * math.exp(-(c*mu - lam) * t)

def minimal_servers(lam: float, mu: float, t_slo: float, alpha: float) -> int:
    # Find minimal c satisfying tail bound for waiting time (M/M/c).
    c = max(1, int(math.ceil(lam / mu)))
    while True:
        if lam >= c*mu:
            c += 1
            continue
        # account for service time in SLO by using waiting time bound
        if tail_wait_prob(c, lam, mu, t_slo) <= alpha:
            return c
        c += 1

# Monte Carlo validator for general service-time sampler
def monte_carlo_validate(arrival_rate: float, service_sampler: Callable[[], float],
                         servers: int, t_slo: float, samples: int = 100_000) -> float:
    # Simplified M/M/c-like simulation using Poisson arrivals and independent service times,
    # approximate queueing via discrete event sampling for latency empirical CDF.
    events = []  # next free times per server
    events = [0.0] * servers
    breaches = 0
    for _ in range(samples):
        # inter-arrival exponential
        ia = random.expovariate(arrival_rate)
        # advance time implicitly by sampling arrival; we track server free times
        # choose earliest free server available
        free_idx = min(range(servers), key=lambda i: events[i])
        start = max(events[free_idx], 0.0)
        service = service_sampler()
        finish = start + service
        latency = finish - 0.0  # arrival at time 0 in this simplified per-request view
        events[free_idx] = finish
        if latency > t_slo:
            breaches += 1
    return breaches / samples

# Example usage:
if __name__ == "__main__":
    lam = 200.0                 # requests/sec measured at edge ingress
    mu = 50.0                   # service rate (1/mean service time)
    t_slo = 0.100               # 100 ms SLO
    alpha = 0.05
    c = minimal_servers(lam, mu, t_slo, alpha)
    print("Minimal servers (Erlang C):", c)
    # validate with measured service-time distribution (replace sampler with real histogram)
    sampler = lambda: random.expovariate(mu)  # replace with empirical sampler
    breach_rate = monte_carlo_validate(lam, sampler, c, t_slo, samples=20000)
    print("Monte Carlo breach rate:", breach_rate)