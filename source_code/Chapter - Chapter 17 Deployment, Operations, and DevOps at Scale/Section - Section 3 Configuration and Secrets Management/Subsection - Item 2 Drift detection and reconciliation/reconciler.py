#!/usr/bin/env python3
# Production-ready reconciler: MQTT subscribe, Redis desired-state, publish reconcile.
import os, json, time, logging, hashlib
import redis, ssl
import paho.mqtt.client as mqtt

# Configuration via environment variables for Kubernetes/Pod security.
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt-broker.svc.cluster.local")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_CERT = os.getenv("MQTT_CERT", "/etc/ssl/certs/ca.pem")
DESIRED_PREFIX = os.getenv("DESIRED_PREFIX", "desired:manifest:")  # Redis key prefix
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DRIFT_THRESHOLD = float(os.getenv("DRIFT_THRESHOLD", "0.0"))  # binary in this example

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
r = redis.from_url(REDIS_URL)

def sha256_of_manifest(manifest: dict) -> str:
    # Canonicalize JSON and compute deterministic SHA256.
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()

def on_connect(client, userdata, flags, rc):
    logging.info("Connected to MQTT broker rc=%s", rc)
    client.subscribe("devices/+/report/manifest")  # wildcard subscriptions

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        device_id = payload["device_id"]
        manifest = payload["manifest"]
        reported_hash = sha256_of_manifest(manifest)
        desired_key = DESIRED_PREFIX + device_id
        desired_hash = r.get(desired_key)
        if desired_hash is None:
            logging.warning("No desired manifest for %s; skipping", device_id)
            return
        desired_hash = desired_hash.decode("utf-8")
        if reported_hash != desired_hash:
            logging.info("Drift detected for %s: reported %s desired %s", device_id, reported_hash, desired_hash)
            # Publish reconcile command; agent must implement secure command handling.
            cmd = {"device_id": device_id, "action": "reconcile_manifest", "target_hash": desired_hash}
            client.publish(f"devices/{device_id}/commands", json.dumps(cmd), qos=1)
            # Record event for audit/observability.
            r.lpush(f"drift:events:{device_id}", json.dumps({"ts": int(time.time()), "reported": reported_hash, "desired": desired_hash}))
        else:
            logging.debug("No drift for %s", device_id)
    except Exception as e:
        logging.exception("Error processing message: %s", e)

def main():
    client = mqtt.Client()
    client.tls_set(ca_certs=MQTT_CERT, certfile=None, keyfile=None, cert_reqs=ssl.CERT_REQUIRED)
    client.on_connect = on_connect
    client.on_message = on_message
    # Keepalive, reconnect handled by loop_forever with backoff.
    while True:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            logging.exception("MQTT connection failed, retrying in 5s: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    main()