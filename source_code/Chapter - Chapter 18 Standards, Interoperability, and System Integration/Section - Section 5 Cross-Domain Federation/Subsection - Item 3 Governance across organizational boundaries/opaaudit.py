#!/usr/bin/env python3
import requests, json, logging
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from datetime import datetime

OPA_URL = "https://localhost:8181/v1/data/federation/allow"  # OPA decision API
AUDIT_COLLECTOR = "https://audit-collector.example.org/ingest"
PRIVATE_KEY_PEM = "/etc/keys/fog_node_priv.pem"

logging.basicConfig(level=logging.INFO)

def load_private_key(path):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None, backend=default_backend())

def query_opa(input_obj):
    resp = requests.post(OPA_URL, json={"input": input_obj}, timeout=5)
    resp.raise_for_status()
    return resp.json().get("result", {})

def sign_record(privkey, record_bytes):
    sig = privkey.sign(record_bytes,
                       padding.PKCS1v15(),
                       hashes.SHA256())
    return sig.hex()

def submit_audit(record, signature):
    payload = {"record": record, "signature": signature}
    resp = requests.post(AUDIT_COLLECTOR, json=payload, timeout=5)
    resp.raise_for_status()
    return resp.status_code

def evaluate_and_audit(actor, resource, action, metadata):
    priv = load_private_key(PRIVATE_KEY_PEM)
    input_obj = {"actor": actor, "resource": resource, "action": action, "metadata": metadata}
    decision = query_opa(input_obj)
    record = {
        "timestamp": datetime.utcnow().isoformat()+"Z",
        "decision": decision,
        "input": input_obj
    }
    record_bytes = json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = sign_record(priv, record_bytes)
    submit_audit(record, signature)
    logging.info("Decision audited; allow=%s", decision.get("allow"))
    return decision.get("allow", False)

# Example call: evaluate_and_audit("domainB:serviceX", "sensor_A1", "read", {"region":"A"})