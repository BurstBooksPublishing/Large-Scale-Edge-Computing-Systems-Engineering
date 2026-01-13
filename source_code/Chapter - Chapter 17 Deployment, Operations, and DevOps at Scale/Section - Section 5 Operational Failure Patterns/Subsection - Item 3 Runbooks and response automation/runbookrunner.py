import asyncio
from kubernetes import config, client
import asyncssh

# Initialize Kubernetes client (in-cluster or kubeconfig)
config.load_kube_config()  # or config.load_incluster_config()
v1 = client.CoreV1Api()

async def cordon_and_drain(node_name, timeout=60):
    # mark schedulable=false
    body = {"spec": {"unschedulable": True}}
    v1.patch_node(node_name, body)
    # evict pods (simple loop; production should use eviction API and respect PDBs)
    end = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < end:
        pods = v1.list_pod_for_all_namespaces(field_selector=f"spec.nodeName={node_name}").items
        non_daemon = [p for p in pods if not any(c.owner_references for c in (p.metadata.owner_references or []))]
        if not non_daemon:
            return True
        await asyncio.sleep(2)
    return False

async def ssh_cleanup(host, user, key):
    # fallback actions: rotate logs and free space
    async with asyncssh.connect(host, username=user, client_keys=[key]) as conn:
        await conn.run('sudo systemctl stop noncritical.service', check=False)  # safe stop
        await conn.run('sudo journalctl --vacuum-size=200M', check=False)
        await conn.run('sudo rm -rf /var/cache/app/*', check=False)
        res = await conn.run('df --output=pcent / | tail -1', check=False)
        return int(res.stdout.strip().strip('%')) < 85

async def run_recovery(node_name, ssh_host, ssh_user, ssh_key):
    ok = await cordon_and_drain(node_name)
    if ok:
        # verify health probe (short)
        return True
    # fallback path
    return await ssh_cleanup(ssh_host, ssh_user, ssh_key)

# example usage
# asyncio.run(run_recovery('edge-node-42', '10.0.0.42', 'admin', '/keys/id_rsa'))