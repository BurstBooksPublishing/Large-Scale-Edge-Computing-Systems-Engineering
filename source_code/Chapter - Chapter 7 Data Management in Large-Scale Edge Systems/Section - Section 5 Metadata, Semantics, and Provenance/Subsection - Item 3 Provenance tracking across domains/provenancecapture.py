#!/usr/bin/env python3
# Portable provenance capture for Linux-based edge nodes (e.g., Jetson, Raspberry Pi)
import sqlite3, json, time, hashlib, logging
import paho.mqtt.client as mqtt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

logging.basicConfig(level=logging.INFO)
DB_PATH = "/var/lib/provenance/prov.db"
MQTT_BROKER = "edge-kafka-proxy.local"  # or use Kafka producer in production
MQTT_TOPIC = "provenance/signed"
AGENT_ID = "spiffe://example.org/agent/edge-node-01"

# Ensure database and append-only table
conn = sqlite3.connect(DB_PATH, isolation_level=None, detect_types=sqlite3.PARSE_DECLTYPES)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("""CREATE TABLE IF NOT EXISTS prov (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    prov_json TEXT NOT NULL,
    hash TEXT NOT NULL,
    signature BLOB NOT NULL
)""")

# In-memory ECDSA key for example. In production, use TPM-backed key.
private_key = ec.generate_private_key(ec.SECP256R1())

def sign_blob(blob: bytes) -> bytes:
    # Returns DER-like signature; replace with PKCS#11/TPM call for HSM
    sig = private_key.sign(blob, ec.ECDSA(hashes.SHA256()))
    return sig

def publish_signed(record: dict, sig: bytes):
    client = mqtt.Client()
    client.connect(MQTT_BROKER, 1883, 60)
    payload = json.dumps({"record": record, "signature": sig.hex()})
    client.publish(MQTT_TOPIC, payload, qos=1)
    client.disconnect()

def capture_provenance(activity_id: str, inputs: list, operator_version: str):
    ts = time.time()
    prov = {
        "agent": AGENT_ID,
        "activity": activity_id,
        "inputs": inputs,
        "operator_version": operator_version,
        "timestamp": ts
    }
    prov_bytes = json.dumps(prov, separators=(",", ":"), sort_keys=True).encode("utf-8")
    h = hashlib.sha256(prov_bytes).hexdigest().encode("ascii")
    sig = sign_blob(prov_bytes)
    # Append to local store atomically
    cur = conn.cursor()
    cur.execute("INSERT INTO prov (timestamp, prov_json, hash, signature) VALUES (?, ?, ?, ?)",
                (ts, prov_bytes.decode("utf-8"), h.decode("ascii"), sig))
    cur.close()
    publish_signed(prov, sig)

# Example use
if __name__ == "__main__":
    capture_provenance("feature-extract:run:2025-12-29T12:00:00Z",
                       ["sensor:temp:hash:abcd1234"], "edge-op:1.2.3")