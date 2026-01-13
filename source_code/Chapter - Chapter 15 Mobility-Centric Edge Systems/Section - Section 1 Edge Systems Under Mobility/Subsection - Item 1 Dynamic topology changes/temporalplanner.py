#!/usr/bin/env python3
from typing import List, Tuple, Dict
import heapq
import networkx as nx
import logging

# Contact: (src, dst, t_start, t_end, bw_bytes_per_s)
Contact = Tuple[str, str, float, float, float]

def build_time_expanded_graph(contacts: List[Contact]) -> nx.DiGraph:
    """Build directed time-expanded graph nodes as (node, time)."""
    G = nx.DiGraph()
    # create time-nodes and edges for contacts and waiting
    for src, dst, t0, t1, bw in contacts:
        G.add_node((src, t0)); G.add_node((dst, t1))
        # edge representing possible transfer window start->end
        G.add_edge((src, t0), (dst, t1), capacity=bw*(t1-t0), duration=t1-t0)
    # add waiting edges per node between successive times
    times_by_node: Dict[str, set] = {}
    for u, v, t0, t1, _ in contacts:
        times_by_node.setdefault(u, set()).add(t0); times_by_node.setdefault(v, set()).add(t1)
    for node, times in times_by_node.items():
        for a, b in sorted(times):
            if a < b:
                G.add_edge((node, a), (node, b), capacity=float('inf'), duration=b-a)
    return G

def earliest_arrival(contacts: List[Contact], source: str, t0: float, target: str, size_bytes: float) -> float:
    """Return earliest arrival time when size_bytes can be delivered, or +inf."""
    G = build_time_expanded_graph(contacts)
    # Dijkstra-like search on time-expanded nodes starting from (source, t0)
    pq = [(t0, (source, t0))]; dist = {(source, t0): t0}
    while pq:
        cur_t, node = heapq.heappop(pq)
        if node[0] == target and cur_t >= node[1]:
            return cur_t
        for nbr in G.successors(node):
            edge = G.edges[node, nbr]
            cap = edge['capacity']
            # only traverse if capacity can carry the payload
            if cap < size_bytes and edge['capacity'] != float('inf'):
                continue
            arrival = nbr[1]
            if arrival < dist.get(nbr, float('inf')):
                dist[nbr] = arrival
                heapq.heappush(pq, (arrival, nbr))
    return float('inf')

# Example usage (to be integrated into orchestration controller).
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    contacts = [
        ("veh1","rsuA",0.0,2.0,5e6),  # 5 MB/s for 2s
        ("rsuA","rsuB",3.0,5.0,2e6),
        ("rsuB","cloud",6.0,10.0,10e6),
    ]
    t_arr = earliest_arrival(contacts,"veh1",0.0,"cloud",20_000_000)
    logging.info("earliest arrival to cloud: %.2f s", t_arr)