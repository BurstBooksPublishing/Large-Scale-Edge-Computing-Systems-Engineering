from nacl.signing import VerifyKey  # PyNaCl for Ed25519 verification
import numpy as np
import base64

# Trusted registry mapping client_id -> verify_key_bytes (provisioned via TPM/secure enrollment)
trusted_keys = {'clientA': b'\x01...'}  # replace with actual keys

def verify_signature(client_id: str, payload: bytes, signature_b64: str) -> bool:
    vk_bytes = trusted_keys.get(client_id)
    if vk_bytes is None:
        return False
    verify_key = VerifyKey(vk_bytes)
    signature = base64.b64decode(signature_b64)
    try:
        verify_key.verify(payload, signature)  # raises on failure
        return True
    except Exception:
        return False

def clip_update(delta: np.ndarray, S: float) -> np.ndarray:
    norm = np.linalg.norm(delta)
    if norm <= S:
        return delta
    return delta * (S / norm)

def is_outlier(delta: np.ndarray, history_mean: np.ndarray, history_std: np.ndarray, z_thresh: float=6.0) -> bool:
    # compute per-parameter z-score; reject if any param z > threshold
    z = np.abs((delta - history_mean) / (history_std + 1e-12))
    return np.any(z > z_thresh)

def process_client_update(client_id: str, delta_bytes: bytes, signature_b64: str,
                          S: float, hist_mean: np.ndarray, hist_std: np.ndarray):
    if not verify_signature(client_id, delta_bytes, signature_b64):
        raise ValueError("Signature verification failed")
    delta = np.frombuffer(delta_bytes, dtype=np.float32)  # model-specific dtype
    delta_clipped = clip_update(delta, S)
    if is_outlier(delta_clipped, hist_mean, hist_std):
        # log, quarantine client, and optionally request re-send or audit
        raise ValueError("Anomalous update detected")
    return delta_clipped