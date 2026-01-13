#!/usr/bin/env bash
set -euo pipefail

IMAGE="$1"                 # e.g., registry.example.com/myapp:1.2.3
CONTAINER_NAME="${2:-edgeapp}"
COSIGN_PUBKEY="/etc/keys/cosign.pub"
RETRIES=5
BACKOFF_BASE=2
HEALTH_URL="http://127.0.0.1:8080/health"
HEALTH_RETRIES=3
LOG="/var/log/edge_lifecycle.log"

log() { printf '%s %s\n' "$(date -Is)" "$*" >>"$LOG"; }

# Pull with retries and platform negotiation
pull_image() {
  for i in $(seq 1 $RETRIES); do
    if ctr images pull --platform linux/arm64,linux/amd64 "$IMAGE"; then
      return 0
    fi
    sleep $(( BACKOFF_BASE ** (i-1) ))
  done
  return 1
}

# Verify signature using cosign; abort on failure
verify_image() {
  cosign verify --key "$COSIGN_PUBKEY" "$IMAGE" >/dev/null 2>&1
}

# Create and start container (detached)
start_container() {
  # Remove old task if exists, then create and start
  if ctr container info "$CONTAINER_NAME" >/dev/null 2>&1; then
    ctr task kill "$CONTAINER_NAME" || true
    ctr container delete "$CONTAINER_NAME" || true
  fi
  ctr container create "$IMAGE" "$CONTAINER_NAME"
  ctr task start -d "$CONTAINER_NAME"
}

# Health check with restart policy
health_loop() {
  local failures=0
  while true; do
    if curl -fsS "$HEALTH_URL" >/dev/null; then
      failures=0
    else
      failures=$((failures+1))
      log "health check failed ($failures)"
      if [ "$failures" -ge "$HEALTH_RETRIES" ]; then
        log "restarting container"
        ctr task kill "$CONTAINER_NAME" || true
        ctr container delete "$CONTAINER_NAME" || true
        start_container
        failures=0
      fi
    fi
    sleep 5
  done
}

log "lifecycle start: $IMAGE"
pull_image
verify_image || { log "signature verification failed"; exit 2; }
start_container
health_loop