from typing import List, Dict, Tuple
import heapq

# Types: task -> (id, cpu_demand, priority), node -> (id, capacity, gpu_flag)
Task = Tuple[str, float, float]
Node = Tuple[str, float, bool]

def greedy_assign(tasks: List[Task], nodes: List[Node],
                  latency: Dict[Tuple[str,str], float],
                  power: Dict[Tuple[str,str], float],
                  alpha: float=1.0, beta: float=0.1
                 ) -> Dict[str,str]:
    # Precompute scores s_{tn}; smaller is better.
    scores = {}
    for tid, c, p in tasks:
        for nid, cap, gpu in nodes:
            scores[(tid,nid)] = alpha * latency[(tid,nid)] + beta * power[(tid,nid)]
    # Order tasks by density = priority / cpu_demand (descending)
    tasks_sorted = sorted(tasks, key=lambda x: x[2]/max(1e-6, x[1]), reverse=True)
    remaining = {nid: cap for nid, cap, _ in nodes}
    assignment = {}
    for tid, c, _ in tasks_sorted:
        # choose feasible node with minimal score
        candidates = [(scores[(tid,nid)], nid) for nid in remaining if remaining[nid] >= c]
        if not candidates:
            # fallback: leave unassigned or mark for cloud
            assignment[tid] = None
            continue
        _, chosen = min(candidates)
        assignment[tid] = chosen
        remaining[chosen] -= c
    return assignment

def pairwise_local_search(assignment: Dict[str,str], tasks: List[Task], nodes: List[Node],
                          latency, power, alpha=1.0, beta=0.1, max_iters=1000):
    # helper: objective contribution of task t on node n
    contrib = lambda tid, nid: alpha*latency[(tid,nid)] + beta*power[(tid,nid)]
    # build reverse index and remaining capacity
    node_caps = {nid: cap for nid, cap, _ in nodes}
    for tid, c, _ in tasks:
        nid = assignment.get(tid)
        if nid is not None:
            node_caps[nid] -= c
    it = 0
    improved = True
    while improved and it < max_iters:
        improved = False
        it += 1
        # iterate over task pairs and attempt swaps
        for i in range(len(tasks)):
            tid_i, ci, _ = tasks[i]
            ni = assignment.get(tid_i)
            for j in range(i+1, len(tasks)):
                tid_j, cj, _ = tasks[j]
                nj = assignment.get(tid_j)
                if ni is None or nj is None or ni == nj:
                    continue
                # capacity after swap
                if node_caps[ni] + ci - cj < 0 or node_caps[nj] + cj - ci < 0:
                    continue
                current = contrib(tid_i, ni) + contrib(tid_j, nj)
                swapped = contrib(tid_i, nj) + contrib(tid_j, ni)
                if swapped + 1e-9 < current:
                    # perform swap
                    assignment[tid_i], assignment[tid_j] = nj, ni
                    node_caps[ni] += ci - cj
                    node_caps[nj] += cj - ci
                    improved = True
            if improved:
                break
    return assignment