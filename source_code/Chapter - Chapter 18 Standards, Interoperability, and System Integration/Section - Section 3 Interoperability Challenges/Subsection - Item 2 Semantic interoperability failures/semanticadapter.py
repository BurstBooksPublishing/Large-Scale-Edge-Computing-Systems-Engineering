import asyncio
from paho.mqtt import client as mqtt  # stable C-backed client
from pint import UnitRegistry
from pydantic import BaseModel
import json

ureg = UnitRegistry()

class InTelemetry(BaseModel):
    sensor_id: str
    attr: str
    value: float
    unit: str = None
    sample_rate_hz: float = None

class NormalizedTelemetry(BaseModel):
    device: str
    attribute: str
    value: float
    unit: str
    timestamp: float

# MQTT callbacks
def on_connect(client, userdata, flags, rc):
    client.subscribe("vendors/+/telemetry")

def convert_to_target(val, from_unit, to_unit):
    if from_unit is None:
        raise ValueError("missing unit metadata")
    return (val * ureg(from_unit)).to(to_unit).magnitude

def on_message(client, userdata, msg):
    try:
        raw = json.loads(msg.payload)
        in_t = InTelemetry(**raw)
        # map vendor attribute names to canonical names
        attr_map = {"accel_rms":"acceleration_rms","vibration_magnitude":"acceleration_rms"}
        canonical = attr_map.get(in_t.attr, in_t.attr)
        # unit canonicalization
        target_unit = "m/s**2"
        val = convert_to_target(in_t.value, in_t.unit, target_unit)
        out = NormalizedTelemetry(device=in_t.sensor_id,
                                  attribute=canonical,
                                  value=val,
                                  unit=target_unit,
                                  timestamp=asyncio.get_event_loop().time())
        client.publish("normalized/telemetry", out.json())
    except Exception as e:
        # minimal logging for edge; route to monitoring pipeline
        client.publish("edge/errors", json.dumps({"err": str(e), "topic": msg.topic}))

def run(broker="localhost"):
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker)
    client.loop_forever()

if __name__ == "__main__":
    run()