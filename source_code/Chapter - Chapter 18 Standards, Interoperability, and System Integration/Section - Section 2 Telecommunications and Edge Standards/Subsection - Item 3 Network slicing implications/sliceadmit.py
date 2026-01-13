#!/usr/bin/env python3
import requests
from kubernetes import client, config
# Simple proportional allocator; replace with convex solver for production.
def allocate_slices(slices, total_cpu):
    # slices: list of dicts {'id','lambda','alpha','min_cpu','weight'}
    # compute minimal CPU to satisfy mu>lambda, with beta*b=0 here
    alloc = {}
    remaining = total_cpu
    for s in sorted(slices, key=lambda x: -x['weight']):  # priority order
        need = max(s['min_cpu'], (s['lambda'] / s['alpha']) + 1e-3)
        if need <= remaining:
            alloc[s['id']] = need
            remaining -= need
        else:
            alloc[s['id']] = None  # reject or partial
    return alloc

# Kubernetes patch to reserve CPU (quota) for a namespace
def reserve_namespace_cpu(ns, cpu_cores):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    rq = client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name="slice-quota"),
        spec=client.V1ResourceQuotaSpec(hard={"requests.cpu": str(cpu_cores)+""})
    )
    v1.create_namespaced_resource_quota(namespace=ns, body=rq)

# Orchestrator call to ONAP/OSM to instantiate slice network functions
def instantiate_slice(onap_url, slice_spec, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(onap_url+"/api/slices", json=slice_spec, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

# Example usage
if __name__ == "__main__":
    slices = [{'id':'url1','lambda':500,'alpha':200.0,'min_cpu':0.2,'weight':10}]
    alloc = allocate_slices(slices, total_cpu=8.0)
    # for admitted slice, reserve namespace and call orchestrator (tokens managed securely)
    for sid, cpu in alloc.items():
        if cpu:
            reserve_namespace_cpu(ns=sid, cpu_cores=cpu)
            # instantiate slice network functions via ONAP (spec omitted for brevity)
            # instantiate_slice(onap_url, slice_spec, token)