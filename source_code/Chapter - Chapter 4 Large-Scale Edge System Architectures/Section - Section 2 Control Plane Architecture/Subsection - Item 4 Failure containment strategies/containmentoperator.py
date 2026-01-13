#!/usr/bin/env python3
# Production-ready operator fragment for failure containment on K8s edge clusters.
import time, requests, os
from kubernetes import client, config, watch

# Configure in-cluster or local kubeconfig
config.load_incluster_config() if os.getenv("KUBERNETES_SERVICE_HOST") else config.load_kube_config()
api = client.NetworkingV1Api()
core = client.CoreV1Api()

NAMESPACE = os.getenv("TARGET_NAMESPACE", "edge-services")
HEALTH_URL = os.getenv("CONTROLLER_HEALTH_URL", "http://10.0.0.5:8080/health")
FAIL_THRESHOLD = int(os.getenv("FAIL_THRESHOLD", "3"))
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))

def make_restrictive_np():
    # Deny egress except to approved endpoints (e.g., local telemetry).
    return client.V1NetworkPolicy(
        metadata=client.V1ObjectMeta(name="restrict-egress-on-failure"),
        spec=client.V1NetworkPolicySpec(
            pod_selector=client.V1LabelSelector(match_labels={}),  # apply to all pods
            policy_types=["Egress"],
            egress=[
                client.V1NetworkPolicyEgressRule(  # allow only local DNS and telemetry
                    to=[client.V1NetworkPolicyPeer(
                        pod_selector=client.V1LabelSelector(match_labels={"role":"telemetry"})
                    )]
                )
            ]
        )
    )

def ensure_configmap_locked():
    # Pin node-local fallback policy to avoid remote pulls during failure.
    cm = client.V1ConfigMap(metadata=client.V1ObjectMeta(name="local-fallback-policy"), data={"mode":"locked"})
    try:
        core.create_namespaced_config_map(NAMESPACE, cm)
    except client.exceptions.ApiException as e:
        if e.status == 409:  # already exists, update
            core.replace_namespaced_config_map("local-fallback-policy", NAMESPACE, cm)

def apply_network_policy():
    np = make_restrictive_np()
    try:
        api.create_namespaced_network_policy(NAMESPACE, np)
    except client.exceptions.ApiException as e:
        if e.status == 409:
            api_replace = api.replace_namespaced_network_policy
            api_replace("restrict-egress-on-failure", NAMESPACE, np)

def main():
    fail_count = 0
    while True:
        try:
            r = requests.get(HEALTH_URL, timeout=2)
            if r.status_code == 200:
                fail_count = 0
            else:
                fail_count += 1
        except requests.RequestException:
            fail_count += 1

        if fail_count >= FAIL_THRESHOLD:
            apply_network_policy()
            ensure_configmap_locked()
            # exponential backoff to limit controller traffic.
            time.sleep(CHECK_INTERVAL * 4)
        else:
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()