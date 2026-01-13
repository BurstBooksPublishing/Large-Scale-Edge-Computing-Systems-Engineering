#!/usr/bin/env bash
set -euo pipefail

IMAGE="$1"                       # e.g., registry.example.com/app:1.2.3
COSIGN_KEY_REF="kms://projects/..../keys/cosign"  # key reference
SBOM_PATH="/tmp/sbom.json"

# 1) Verify image signature with cosign (uses KMS/HSM-backed key)
cosign verify --key "$COSIGN_KEY_REF" "$IMAGE"

# 2) Pull SBOM and verify signature (SBOM published at artifact registry)
curl -fsSL "https://registry.example.com/artifacts/${IMAGE}/sbom" -o "$SBOM_PATH"
# SBOM signature verification (assumes detached signature .sig)
gpg --verify "${SBOM_PATH}.sig" "$SBOM_PATH"

# 3) Basic SBOM policy check: fail on forbidden packages
if jq -e '.packages[] | select(.name=="openssl" and .version | test("^1\\.0"))' "$SBOM_PATH" >/dev/null; then
  echo "Policy violation: vulnerable openssl present" >&2
  exit 1
fi

# 4) Trigger canary deployment to k3s (namespace and label denote canary)
kubectl set image deployment/app app="$IMAGE" -n factory-canary
kubectl rollout status deployment/app -n factory-canary --timeout=120s

# 5) Monitor for anomalies (placeholder for real observability hooks)
# If checks pass, promote to production namespace
kubectl set image deployment/app app="$IMAGE" -n factory-prod