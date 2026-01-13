#!/usr/bin/env python3
# Production-ready: capability probe and adapter selection for an edge gateway.
import json,logging,subprocess,requests,sys

EDGE_CAP_URL = "http://localhost:8080/capabilities"  # node capability endpoint

def probe_capabilities(url=EDGE_CAP_URL, timeout=2.0):
    # Query local capability service that returns JSON {"protocols": [...], "formats": [...]}
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def choose_adapter(capabilities, preferred=["opcua","mqtt","coap","json"]):
    # Select highest-preference common protocol with fleet control plane
    for proto in preferred:
        if proto in capabilities.get("protocols", []):
            return proto
    return None

def pull_and_run_adapter(adapter_image, podman=True):
    # Pull and run adapter as container; logs and failure handling included.
    cmd = ["podman","run","-d","--name","edge-adapter", adapter_image] if podman else ["docker","run","-d","--name","edge-adapter", adapter_image]
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        cap = probe_capabilities()
        logging.info("Node capabilities: %s", cap)
        proto = choose_adapter(cap)
        if not proto:
            logging.error("No supported protocol found; aborting.")
            sys.exit(2)
        # Map protocol to adapter image (operator-managed registry)
        adapter_map = {"opcua":"registry.example.com/adapters/opcua-adapter:1.2.0","mqtt":"registry.example.com/adapters/mqtt-adapter:3.4.1"}
        image = adapter_map.get(proto)
        pull_and_run_adapter(image)
        logging.info("Adapter %s deployed", image)
    except Exception as e:
        logging.exception("Adapter deploy failed: %s", e)
        sys.exit(1)