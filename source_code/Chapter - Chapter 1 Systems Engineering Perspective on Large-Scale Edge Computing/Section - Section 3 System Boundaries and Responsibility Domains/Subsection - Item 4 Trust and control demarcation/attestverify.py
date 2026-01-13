import os
import time
import jwt  # PyJWT
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Load verifier public key (PEM) from secure store
with open(os.environ['VERIFIER_PUBKEY_PEM'], 'rb') as f:
    PUBKEY = serialization.load_pem_public_key(f.read(), backend=default_backend())

TAU_CONTROL = 0.85  # threshold for control actions

def verify_attestation(token: str, required_cap: str) -> bool:
    # Verify signature and expiration; raises on failure
    claims = jwt.decode(token, PUBKEY, algorithms=['RS256'], options={'require': ['exp','iat','iss']})
    # Check freshness and simple anti-replay
    if abs(time.time() - claims['iat']) > 300:
        return False
    # Capability and trust score checks
    caps = claims.get('capabilities', [])
    trust_score = float(claims.get('trust_score', 0.0))
    owner = claims.get('owner')
    # Enforce owner-to-action mapping (could query policy DB)
    if required_cap not in caps:
        return False
    if trust_score < TAU_CONTROL:
        return False
    # Example additional check: owner must match allowed operator list
    if owner not in os.environ['ALLOWED_OPERATORS'].split(','):
        return False
    return True

# Example usage in control request handler (framework-specific)
# if verify_attestation(jwt_token, 'actuate_valve'):
#     proceed with control; else deny and audit