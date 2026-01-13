#!/usr/bin/env bash
set -euo pipefail
# /usr/local/bin/decrypt_and_inject.sh
ENC_FILE="/etc/config/secret.enc.yaml"   # encrypted in Git with sops
OUT_FILE="/run/secrets/app.yaml"
LOG="/var/log/decrypt_and_inject.log"

# Ensure sops is present and executable
command -v sops >/dev/null || { echo "sops missing" >>"$LOG"; exit 1; }

# Decrypt to a tmp file with strict perms
TMP="$(mktemp --tmpdir sops.XXXXXX)"
chmod 600 "$TMP"
sops --decrypt "$ENC_FILE" > "$TMP"

# validate YAML (optional): requires yq on edge image
if command -v yq >/dev/null; then
  yq e '.' "$TMP" >/dev/null || { echo "YAML validation failed" >>"$LOG"; rm -f "$TMP"; exit 2; }
fi

# atomically publish to runtime location
umask 077
mv "$TMP" "$OUT_FILE"
chmod 600 "$OUT_FILE"
echo "$(date --iso-8601=seconds) decrypted secrets to $OUT_FILE" >>"$LOG"

# notify systemd service if present
if systemctl --version >/dev/null 2>&1; then
  systemctl --no-block restart app.service || true
fi