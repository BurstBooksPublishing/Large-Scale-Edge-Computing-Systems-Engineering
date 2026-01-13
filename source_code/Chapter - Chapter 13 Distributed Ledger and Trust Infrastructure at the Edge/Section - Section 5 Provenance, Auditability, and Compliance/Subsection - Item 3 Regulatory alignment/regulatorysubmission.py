#!/usr/bin/env python3
# Minimal, production-ready: use secure key storage (TPM/TEE) in production.
import json, time, requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization, hashes

LEDGER_GATEWAY = "https://ledger-gateway.example/api/v1/provenance"
DEVICE_ID = "edge-node-42"

def sign_provenance(priv_key_pem: bytes, record: dict) -> dict:
    # Load private key (replace with TPM-backed key retrieval)
    priv = Ed25519PrivateKey.from_private_bytes(
        serialization.load_pem_private_key(priv_key_pem, password=None).private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()))
    payload = json.dumps(record, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = priv.sign(payload)
    return {"record": record, "signature": sig.hex()}

def submit_to_gateway(signed_blob: dict, timeout=5.0):
    # Use MTLS in production; here we assume bearer token or client certs configured.
    resp = requests.post(LEDGER_GATEWAY, json=signed_blob, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

# Example invocation
if __name__ == "__main__":
    # In prod: retrieve key from secure element, do not load PEM from filesystem.
    with open("/var/lib/keys/ed25519_priv.pem","rb") as f:
        priv_pem = f.read()
    prov = {"device": DEVICE_ID, "ts": int(time.time()), "event": "sensor_read",
            "digest": "sha256:..." }  # compute actual digest
    signed = sign_provenance(priv_pem, prov)
    result = submit_to_gateway(signed)
    print("gateway_result:", result)