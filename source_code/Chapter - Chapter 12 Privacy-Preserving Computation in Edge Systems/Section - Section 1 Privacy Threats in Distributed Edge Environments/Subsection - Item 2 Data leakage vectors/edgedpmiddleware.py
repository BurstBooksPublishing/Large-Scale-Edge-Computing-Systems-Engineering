#!/usr/bin/env python3
# Production-ready MQTT middleware: redact PII and add Laplace noise for numeric aggregates.
import json
import math
import logging
from typing import Dict
import paho.mqtt.client as mqtt
import secrets

BROKER = "localhost"
IN_TOPIC = "devices/+/telemetry"
OUT_TOPIC_PREFIX = "sanitized/"
LOG = logging.getLogger("edge_dp")
LOG.setLevel(logging.INFO)

def laplace_noise(scale: float) -> float:
    # Sample Laplace(0, scale) using inverse CDF
    u = secrets.randbelow(10**9) / 10**9 - 0.5
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))

def sanitize_payload(payload: Dict, numeric_fields: Dict[str,float], redaction_keys):
    # Redact sensitive keys and add noise to specified numeric fields.
    for k in list(payload.keys()):
        if k in redaction_keys:
            payload[k] = "[REDACTED]"
    for field, scale in numeric_fields.items():
        if field in payload and isinstance(payload[field], (int, float)):
            noise = laplace_noise(scale)  # \lstinline|scale| chosen per privacy budget
            payload[field] = float(payload[field]) + noise
    return payload

def on_connect(client, userdata, flags, rc):
    LOG.info("connected rc=%s", rc)
    client.subscribe(IN_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
    except Exception:
        LOG.exception("invalid json")
        return
    # Configure per-deployment parameters
    redaction_keys = {"owner_id", "operator_name"}
    numeric_fields = {"vibration_rms": 0.5, "temperature": 0.1}  # scale = sensitivity/epsilon
    cleaned = sanitize_payload(payload, numeric_fields, redaction_keys)
    out_topic = OUT_TOPIC_PREFIX + msg.topic
    client.publish(out_topic, json.dumps(cleaned), qos=1)
    LOG.debug("published sanitized to %s", out_topic)

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER)
    client.loop_forever()

if __name__ == "__main__":
    main()