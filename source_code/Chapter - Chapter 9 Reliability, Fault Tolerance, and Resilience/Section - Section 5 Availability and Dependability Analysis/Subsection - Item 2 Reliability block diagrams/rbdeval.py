"""Reliability Block Diagram evaluator.
Supports components with failure_rate (lambda) and repair_rate (mu).
Nodes: 'component', 'series', 'parallel', 'kofn'.
"""
from typing import Dict, List, Union
from math import comb

Node = Dict[str, Union[str, float, List['Node'], int]]

def availability_from_rates(lambda_rate: float, mu_rate: float) -> float:
    # steady-state availability for exponential failure/repair
    return mu_rate / (lambda_rate + mu_rate)

def eval_rbd(node: Node) -> float:
    kind = node['type']
    if kind == 'component':
        return availability_from_rates(float(node['lambda']), float(node['mu']))
    if kind == 'series':
        prod = 1.0
        for child in node['children']:
            prod *= eval_rbd(child)
        return prod
    if kind == 'parallel':
        prod_unavail = 1.0
        for child in node['children']:
            prod_unavail *= (1.0 - eval_rbd(child))
        return 1.0 - prod_unavail
    if kind == 'kofn':
        k = int(node['k'])
        avails = [eval_rbd(c) for c in node['children']]
        # handle non-identical component availabilities with binomial convolution
        n = len(avails)
        # dynamic programming convolution of Bernoulli PGFs
        dp = [1.0] + [0.0]*n
        for p in avails:
            for j in range(n, 0, -1):
                dp[j] = dp[j] * (1-p) + dp[j-1] * p
            dp[0] *= (1-p)
        return sum(dp[j] for j in range(k, n+1))
    raise ValueError(f"Unknown node type: {kind}")

# Example usage as a testable routine:
if __name__ == "__main__":
    # three-node parallel compute service example
    comp = lambda_idict: {'type':'component','lambda':lambda_idict[0],'mu':lambda_idict[1]}
    rbd = {'type':'parallel','children':[
        {'type':'component','lambda':0.01,'mu':2.0},
        {'type':'component','lambda':0.01,'mu':2.0},
        {'type':'component','lambda':0.01,'mu':2.0},
    ]}
    print(f"System availability: {eval_rbd(rbd):.9f}")