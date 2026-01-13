#!/usr/bin/env bash
set -euo pipefail
IMAGE_ORG="myorg"
IMAGE_NAME="vision"
TAG="1.2.0"
REGISTRY="registry.example.com"
FULL="${REGISTRY}/${IMAGE_ORG}/${IMAGE_NAME}:${TAG}"

# Ensure buildx builder exists and uses QEMU for cross builds.
docker buildx create --use --name builder || true
docker run --rm --privileged tonistiigi/binfmt --install all  # enable qemu

# Multi-arch build and push (linux/amd64,linux/arm64)
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  --push \
  -t "${FULL}" \
  --label "org.opencontainers.image.revision=$(git rev-parse --short HEAD)" \
  -f Dockerfile .

# Sign image with cosign (assumes COSIGN_PASSWORD in env and key already created)
cosign sign --key cosign.key "${FULL}"

# Verify signature (fail fast)
cosign verify --key cosign.pub "${FULL}"

# Trigger Harbor replication (example: replication rule with ID 7)
# Replace with appropriate API endpoint, credentials must be securely stored.
HARBOR_API="https://harbor-region.example.com/api/v2.0/replication/executions"
API_USER="ci-bot"
API_PASS_FILE="/run/secrets/harbor_password"  # mount from secret store
curl -fsS -u "${API_USER}:$(cat ${API_PASS_FILE})" \
  -H "Content-Type: application/json" \
  -d "{\"trigger\":1,\"policy_id\":7}" "${HARBOR_API}"