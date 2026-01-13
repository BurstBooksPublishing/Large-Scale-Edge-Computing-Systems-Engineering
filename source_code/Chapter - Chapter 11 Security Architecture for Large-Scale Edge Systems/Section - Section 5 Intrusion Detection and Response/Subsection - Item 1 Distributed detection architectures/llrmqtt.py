# Requirements: paho-mqtt, cryptography, requests
# Node: compute local_score(), sign, publish JSON to topic 'edge/llr/{site_id}'
# Aggregator: subscribe, verify signature, sum LLRs, call containment API if threshold exceeded

import json, time, base64, threading
import paho.mqtt.client as mqtt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
import requests

# ----- Configuration -----
BROKER = "mqtt-broker.example.local"
PORT = 8883
TLS_CA = "/etc/ssl/ca.pem"
NODE_KEY = "/etc/edge/ecdsa_node_key.pem"         # device private key (secure storage recommended)
NODE_PUB = "/etc/edge/ecdsa_node_pub.pem"
AGG_PUB_KEYS = { "node-01": "/etc/agg/node-01_pub.pem" }  # aggregator maintains known pub keys
SITE_ID = "node-01"
TOPIC = f"edge/llr/{SITE_ID}"
AGG_TOPIC = "edge/llr/#"
FUSION_THRESHOLD = 10.0
CONTAINMENT_API = "https://orchestrator.example.local/contain"

# ----- Crypto helpers -----
def load_private(path):
    with open(path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)
def sign_bytes(priv, data: bytes) -> str:
    sig = priv.sign(data, ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(sig).decode()

def verify_signature(pub_pem_path, data: bytes, sig_b64: str) -> bool:
    pub = load_pem_public_key(open(pub_pem_path,"rb").read())
    sig = base64.b64decode(sig_b64)
    try:
        pub.verify(sig, data, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False

# ----- Node logic -----
def local_score():
    # Replace with real model inference (lightweight classifier or rule engine)
    # Return an LLR-like float; here a placeholder that samples anomaly score
    import random
    return random.gauss(0.1, 1.0)

def node_publisher():
    priv = load_private(NODE_KEY)
    client = mqtt.Client(client_id=SITE_ID)
    client.tls_set(ca_certs=TLS_CA)
    client.connect(BROKER, PORT)
    client.loop_start()
    try:
        while True:
            score = local_score()
            payload = {"site": SITE_ID, "ts": int(time.time()), "llr": score}
            raw = json.dumps(payload).encode()
            sig = sign_bytes(priv, raw)
            envelope = {"payload": payload, "sig": sig}
            client.publish(TOPIC, json.dumps(envelope), qos=1)
            time.sleep(1.0)  # decision window
    finally:
        client.loop_stop()

# ----- Aggregator logic -----
class Aggregator:
    def __init__(self):
        self.client = mqtt.Client(client_id="aggregator")
        self.client.tls_set(ca_certs=TLS_CA)
        self.client.on_message = self.on_message
        self.sum_llr = {}  # per window sums

    def start(self):
        self.client.connect(BROKER, PORT)
        self.client.subscribe(AGG_TOPIC, qos=1)
        self.client.loop_start()

    def on_message(self, client, userdata, msg):
        try:
            envelope = json.loads(msg.payload.decode())
            payload_raw = json.dumps(envelope["payload"]).encode()
            site = envelope["payload"]["site"]
            sig = envelope["sig"]
            pub_path = AGG_PUB_KEYS.get(site)
            if not pub_path or not verify_signature(pub_path, payload_raw, sig):
                return  # drop unverified
            llr = float(envelope["payload"]["llr"])
            window = int(envelope["payload"]["ts"] / 1)  # per-second windows
            key = (site, window)
            self.sum_llr[key] = self.sum_llr.get(key, 0.0) + llr
            # simple regional fusion: sum across sites for current window
            total = sum(v for k,v in self.sum_llr.items() if k[1]==window)
            if total > FUSION_THRESHOLD:
                requests.post(CONTAINMENT_API, json={"window": window, "score": total}, timeout=2.0)
        except Exception:
            pass

if __name__ == "__main__":
    # Launch node and aggregator in threads for demonstration only
    threading.Thread(target=node_publisher, daemon=True).start()
    agg = Aggregator()
    agg.start()
    while True:
        time.sleep(10)