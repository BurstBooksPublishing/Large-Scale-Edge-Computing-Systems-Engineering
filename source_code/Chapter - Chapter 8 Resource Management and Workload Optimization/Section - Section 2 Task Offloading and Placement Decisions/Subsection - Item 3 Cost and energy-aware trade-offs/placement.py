# Placement chooser: compute score and bind pod to node via Kubernetes API.
import math, requests
from kubernetes import client, config

# Normalize helper
def normalize(v, vmin, vmax):
    return (v - vmin) / (vmax - vmin + 1e-9)

def estimate_energy(exec_secs, power_w, bytes_out, eps_j_per_byte):
    return exec_secs * power_w + bytes_out * eps_j_per_byte

def choose_node(task, nodes, prometheus_url, pricing, weights):
    # task: {'cpu_sec':..., 'bytes_out':..., 'sla_ms':...}
    # nodes: list of metadata with 'name','speed','power_active','eps','rtt_ms','avail_cpu','avail_mem'
    scores=[]
    # bounds for normalization
    latencies=[n['rtt_ms']+1000*task['cpu_sec']/n['speed'] for n in nodes]
    energies=[estimate_energy(1000*task['cpu_sec']/n['speed'], n['power_active'], task['bytes_out'], n['eps']) for n in nodes]
    costs=[(task['cpu_sec']/3600.0)*pricing.get(n['type'],0) for n in nodes]
    for i,n in enumerate(nodes):
        latency = n['rtt_ms'] + 1000*task['cpu_sec']/n['speed']
        energy = estimate_energy(1000*task['cpu_sec']/n['speed'], n['power_active'], task['bytes_out'], n['eps'])
        cost = (task['cpu_sec']/3600.0)*pricing.get(n['type'],0) + (task['bytes_out']/1e9)*pricing.get('egress',0)
        if latency > task['sla_ms'] or n['avail_cpu'] < task['cpu_sec'] or n['avail_mem'] < task.get('mem_mb',0):
            continue
        nl = normalize(latency, min(latencies), max(latencies))
        ne = normalize(energy, min(energies), max(energies))
        nc = normalize(cost, min(costs), max(costs))
        score = weights['latency']*nl + weights['energy']*ne + weights['cost']*nc
        scores.append((score,n['name']))
    if not scores:
        raise RuntimeError("No feasible node")
    scores.sort()
    return scores[0][1]

# Example usage (fill prometheus, pricing, and nodes from environment/monitoring)
# After selection, use Kubernetes Python client to patch pod.spec.nodeSelector or create binding.