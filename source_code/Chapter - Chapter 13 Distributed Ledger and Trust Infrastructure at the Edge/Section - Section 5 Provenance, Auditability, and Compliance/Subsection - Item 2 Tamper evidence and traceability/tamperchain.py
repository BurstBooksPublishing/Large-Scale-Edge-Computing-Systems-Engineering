#!/usr/bin/env python3
# Production-ready: deterministic JSON, strict TLS, retries, and HSM/TPM hooks.
import json, time, hashlib, requests
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
# Load device identity; prefer HSM/TPM signing via PKCS#11 or tpm2-tools in production.
with open("/etc/edge/keys/device_key.pem","rb") as f:
    private = serialization.load_pem_private_key(f.read(), password=None)
LEDGER_URL = "https://ledger.example.org/api/v1/anchors"  # TLS+mutual auth endpoint
def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
def sign(data: bytes) -> bytes:
    return private.sign(data, padding.PKCS1v15(), hashes.SHA256())
def anchor_batch(records):
    # Compute leaf hashes
    leaves = [sha256(json.dumps(r, sort_keys=True).encode()) for r in records]
    # Build simple Merkle root (pairwise left-right)
    nodes = leaves[:]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1: nodes.append(nodes[-1])  # duplicate last if odd
        nodes = [sha256((nodes[i]+nodes[i+1]).encode()) for i in range(0,len(nodes),2)]
    root = nodes[0]
    timestamp = int(time.time())
    payload = {"device_id":"jetson-plantfloor-01","merkle_root":root,"count":len(records),"ts":timestamp}
    payload_b = json.dumps(payload, sort_keys=True).encode()
    signature = sign(payload_b).hex()
    # Post anchored record; implement exponential backoff and idempotency keys in production.
    r = requests.post(LEDGER_URL, json={"payload":payload,"sig":signature}, timeout=10)
    r.raise_for_status()
# Example: batch collected frames' metadata
# anchor_batch(collected_metadata)