#!/usr/bin/env python3
# Production-ready: robust reconnects, schema validation, unit conversion.
import json, logging
import paho.mqtt.client as mqtt
from pint import UnitRegistry
from jsonschema import validate, ValidationError

U = UnitRegistry()
BROKER = "localhost"
IN_TOPIC = "site/+/raw"
OUT_TOPIC = "site/{site}/normalized"
JSON_LD_CONTEXT = {"vibration_rms": "http://example.org/vocab#vibration_rms"}

# minimal schema for normalized message
NORMAL_SCHEMA = {
  "type": "object",
  "properties": {
    "site": {"type": "string"},
    "timestamp": {"type": "string"},
    "vibration_rms": {"type": "number"},
    "unit": {"type": "string"}
  },
  "required": ["site","timestamp","vibration_rms","unit"]
}

def convert_to_m_s2(value, unit_str):
    q = value * U(unit_str)
    return q.to("meter/second**2").magnitude

def on_message(client, userdata, msg):
    try:
        rec = json.loads(msg.payload)
        # map lexical variants to canonical term
        site = rec.get("site") or "unknown"
        raw_val = rec.get("acc_rms_g") or rec.get("vibration_rms")
        unit = "g" if "acc_rms_g" in rec else rec.get("unit","m/s^2")
        if raw_val is None:
            logging.warning("missing value; ignoring")
            return
        # unit-aware conversion
        try:
            normalized = convert_to_m_s2(float(raw_val), unit)
        except Exception:
            logging.exception("unit conversion failed")
            return
        out = {"site": site, "timestamp": rec.get("ts"), 
               "vibration_rms": normalized, "unit": "m/s^2"}
        validate(out, NORMAL_SCHEMA)  # schema enforcement
        client.publish(OUT_TOPIC.format(site=site), json.dumps(out), qos=1)
    except (json.JSONDecodeError, ValidationError):
        logging.exception("malformed message")

def main():
    client = mqtt.Client()
    client.on_message = on_message
    client.connect(BROKER)
    client.subscribe(IN_TOPIC, qos=1)
    client.loop_forever()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()