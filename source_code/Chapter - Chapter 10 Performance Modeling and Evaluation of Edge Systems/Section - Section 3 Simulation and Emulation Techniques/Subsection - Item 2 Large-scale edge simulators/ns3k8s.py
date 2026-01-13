#!/usr/bin/env python3
# Submit parameterized ns-3 jobs to Kubernetes with node affinity and resource requests.
from kubernetes import client, config
import math, uuid

# Load kubeconfig or in-cluster config
config.load_kube_config()  # use load_incluster_config() on cluster

batch = client.BatchV1Api()
namespace = "edge-sim"
image = "myregistry/ns3:latest"  # container with ns-3 and scenario scripts
sim_count = 20
cores_per_job = 4
memory_per_job = "8Gi"

for i in range(sim_count):
    job_name = f"ns3-sim-{uuid.uuid4().hex[:8]}"
    # Command runs scenario script with parameters passed via args
    cmd = ["bash", "-c", f"/opt/ns3/run_scenario.sh --nodes=1000 --seed={i}"]
    job = client.V1Job(
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            backoff_limit=2,
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name="ns3",
                            image=image,
                            command=cmd,
                            resources=client.V1ResourceRequirements(
                                requests={"cpu": str(cores_per_job), "memory": memory_per_job},
                                limits={"cpu": str(cores_per_job), "memory": memory_per_job}
                            ),
                            volume_mounts=[]  # mount config or HIL endpoints as needed
                        )
                    ],
                    node_selector={"edge-accelerator": "jetson"},  # HIL co-location
                    tolerations=[],  # add if scheduling to tainted nodes
                )
            )
        )
    )
    batch.create_namespaced_job(namespace=namespace, body=job)
    print(f"Submitted job {job_name}")