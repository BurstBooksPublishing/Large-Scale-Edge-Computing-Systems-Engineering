#!/usr/bin/env python3
# production-ready watcher: detect federation controller loss and apply local fallback CRD
import logging, time, os
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from tenacity import retry, wait_exponential, stop_after_attempt

logging.basicConfig(level=logging.INFO)
config.load_kube_config()  # respects KUBECONFIG or in-cluster config
api = client.CustomObjectsApi()
core_v1 = client.CoreV1Api()

FED_NAMESPACE = os.getenv("FED_NAMESPACE", "federation-system")
CONTROLLER_NAME = os.getenv("CONTROLLER_NAME", "kubefed-controller")
LOCAL_OVERRIDE_GROUP = "edge.example.com"
LOCAL_OVERRIDE_VERSION = "v1"
LOCAL_OVERRIDE_PLURAL = "localoverrides"
CLUSTER_NAME = os.getenv("CLUSTER_NAME", "region-a")

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def is_controller_healthy():
    # check controller pod readiness as health proxy
    pods = core_v1.list_namespaced_pod(FED_NAMESPACE, label_selector=f"app={CONTROLLER_NAME}")
    for p in pods.items:
        for c in p.status.conditions or []:
            if c.type == "Ready" and c.status == "True":
                return True
    raise RuntimeError("controller not ready")

def apply_local_override():
    body = {
        "apiVersion": f"{LOCAL_OVERRIDE_GROUP}/{LOCAL_OVERRIDE_VERSION}",
        "kind": "LocalOverride",
        "metadata": {"name": f"fallback-{CLUSTER_NAME}"},
        "spec": {"enforce": True, "reason": "federation-controller-unreachable"}
    }
    try:
        api.create_namespaced_custom_object(LOCAL_OVERRIDE_GROUP, LOCAL_OVERRIDE_VERSION,
                                            "default", LOCAL_OVERRIDE_PLURAL, body)
        logging.info("Applied LocalOverride CRD")
    except ApiException as e:
        if e.status == 409:
            logging.info("LocalOverride exists; reconciled")
            api.patch_namespaced_custom_object(LOCAL_OVERRIDE_GROUP, LOCAL_OVERRIDE_VERSION,
                                               "default", LOCAL_OVERRIDE_PLURAL, body)
        else:
            raise

def main_loop():
    w = watch.Watch()
    backoff = 1
    while True:
        try:
            if not is_controller_healthy():
                apply_local_override()
            else:
                # ensure override is removed when controller healthy
                try:
                    api.delete_namespaced_custom_object(LOCAL_OVERRIDE_GROUP, LOCAL_OVERRIDE_VERSION,
                                                        "default", LOCAL_OVERRIDE_PLURAL,
                                                        f"fallback-{CLUSTER_NAME}")
                    logging.info("Removed LocalOverride")
                except ApiException as e:
                    if e.status != 404:
                        raise
            backoff = 1
        except Exception as exc:
            logging.exception("health-check cycle failed")
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

if __name__ == "__main__":
    main_loop()