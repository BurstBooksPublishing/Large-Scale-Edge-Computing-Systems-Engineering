#!/usr/bin/env python3
# Provenance capture: record, sign, compute merkle root, anchor via REST to ledger gateway
import sqlite3, time, json, hashlib, requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

DB = "/var/lib/provenance/prov.db"
LEDGER_GATEWAY = "https://ledger-gateway.example.net/anchor"  # accepts {"root":hex,...}

# load private key from secure keystore (production: use TPM or PKCS11)
with open("/etc/keys/ecdsa_private.pem", "rb") as f:
    PRIVATE_KEY = serialization.load_pem_private_key(f.read(), password=None)

def canonical_serialize(obj):
    return json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")

def sha256(data):
    return hashlib.sha256(data).digest()

def sign_blob(blob):
    sig = PRIVATE_KEY.sign(blob, ec.ECDSA(hashes.SHA256()))
    return sig.hex()

def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS records(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          vertex_type TEXT,
          payload BLOB,
          hash BLOB,
          signature TEXT,
          timestamp INTEGER
        )""")

def record_vertex(vertex_type, metadata, parent_hashes):
    payload = {
        "type": vertex_type,
        "metadata": metadata,
        "parents": [h.hex() for h in parent_hashes]
    }
    ser = canonical_serialize(payload)
    combined = ser + b"".join(parent_hashes)
    h = sha256(combined)
    sig = sign_blob(h)
    ts = int(time.time())
    with sqlite3.connect(DB) as c:
        c.execute("INSERT INTO records(vertex_type,payload,hash,signature,timestamp) VALUES(?,?,?,?,?)",
                  (vertex_type, ser, h, sig, ts))
    return h

def compute_merkle_root(hashes):
    # simple binary Merkle tree, left-pad duplicate for odd count
    nodes = [h for h in hashes]
    while len(nodes) > 1:
        if len(nodes) % 2 == 1:
            nodes.append(nodes[-1])
        nodes = [sha256(nodes[i] + nodes[i+1]) for i in range(0, len(nodes), 2)]
    return nodes[0] if nodes else sha256(b"")

def anchor_roots():
    with sqlite3.connect(DB) as c:
        cur = c.execute("SELECT hash FROM records WHERE timestamp > ?",
                        (int(time.time()) - 3600,))  # example: last hour
        hashes = [row[0] for row in cur.fetchall()]
    root = compute_merkle_root(hashes)
    payload = {"root": root.hex(), "node_id": "edge-node-42", "timestamp": int(time.time())}
    # authenticated call to operator ledger gateway (TLS client auth recommended)
    r = requests.post(LEDGER_GATEWAY, json=payload, timeout=5)
    r.raise_for_status()
    return r.json()

# usage: called by measurement pipeline
if __name__ == "__main__":
    init_db()
    # example: record a sensor artifact
    meta = {"device":"stm32-12","firmware_hash":"abc123", "value": 0.0123}
    parent_hashes = []
    h = record_vertex("artifact", meta, parent_hashes)
    print("recorded hash", h.hex())
    # periodically anchor
    # resp = anchor_roots()