#!/usr/bin/env python3
# Compute upstream capacity and emit FRR BGP neighbor templates for aggregation nodes.

from typing import List
import math
import json

def required_upstream_capacity(rates: List[float], oversub: float=2.0, redundancy: float=0.5) -> float:
    """rates in Mbps; oversub is target O; redundancy is fractional extra capacity."""
    total = sum(rates)
    base = total / oversub
    return base * (1.0 + redundancy)

def bgp_template(node_name: str, neighbor_ip: str, asn: int, peer_asn: int) -> str:
    """Return a minimal FRR BGP neighbor config snippet."""
    return f"""router bgp {asn}
 bgp router-id {node_name}
 neighbor {neighbor_ip} remote-as {peer_asn}
 neighbor {neighbor_ip} ebgp-multihop 2
 neighbor {neighbor_ip} next-hop-self
!
"""

if __name__ == "__main__":
    # Example inputs for a site gateway aggregating 1000 devices at 0.05 Mbps each.
    device_rates = [0.05]*1000  # Mbps
    upstream = required_upstream_capacity(device_rates, oversub=2.0, redundancy=0.5)
    print(json.dumps({"total_peak_Mbps": sum(device_rates), "upstream_Mbps": round(upstream,3)}))
    # Emit BGP template for operator integration.
    print(bgp_template("site-gw-01", "198.51.100.1", asn=65010, peer_asn=64512))