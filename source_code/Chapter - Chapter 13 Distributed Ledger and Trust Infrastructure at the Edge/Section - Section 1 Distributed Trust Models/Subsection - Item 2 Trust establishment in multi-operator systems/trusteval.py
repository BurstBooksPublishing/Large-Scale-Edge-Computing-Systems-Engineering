#!/usr/bin/env python3
# Requires: requests, cryptography, pyjwt
import time
import requests
import jwt  # PyJWT
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# Fetch operator manifest (JWKs + policy) from ledger-backed URL
def fetch_manifest(url):
    r = requests.get(url, timeout=5)
    r.raise_for_status()
    return r.json()

# Verify attestation token signature and timestamp freshness
def verify_attestation(att_token, jwk_set, max_age=120):
    header = jwt.get_unverified_header(att_token)
    kid = header.get("kid")
    key = next((k for k in jwk_set["keys"] if k["kid"]==kid), None)
    if not key:
        raise ValueError("unknown key id")
    pub = jwt.algorithms.RSAAlgorithm.from_jwk(key)
    payload = jwt.decode(att_token, pub, algorithms=[header["alg"]], options={"verify_aud":False})
    ts = payload.get("iat") or payload.get("timestamp")
    if not ts or abs(time.time() - ts) > max_age:
        raise ValueError("stale attestation")
    return payload

# Compute simple weighted trust score per Eq. (1)
def compute_trust_score(attestation_payload, manifest, sla_reliability, weights=(0.5,0.3,0.2)):
    # A: attestation integrity (1.0 if measurements match policy)
    measurements = attestation_payload.get("measurements", {})
    policy_accept = manifest.get("policy", {}).get("acceptable_measurements", {})
    A = 1.0 if measurements.items() >= policy_accept.items() else 0.0
    # P: provenance/registry validation (0 or 1 for simplicity)
    P = 1.0 if manifest.get("verified", False) else 0.0
    # S: SLA reliability between 0 and 1
    S = max(0.0, min(1.0, sla_reliability))
    wa, wp, ws = weights
    return wa*A + wp*P + ws*S

# Usage example (should be invoked by control-plane orchestrator)
if __name__ == "__main__":
    manifest = fetch_manifest("https://ledger.example/operators/o2/manifest.json")
    jwks = manifest["jwks"]
    att = "eyJ..."  # attestation JWT obtained from node
    payload = verify_attestation(att, jwks)
    sla = 0.98  # e.g., SLA score computed from telemetry
    trust = compute_trust_score(payload, manifest, sla)
    print(f"trust={trust:.3f}")