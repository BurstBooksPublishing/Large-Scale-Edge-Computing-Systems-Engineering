#!/usr/bin/env python3
# Production-ready, asyncio-based adapter for CoAP(CBOR) -> MQTT(JSON)
import asyncio, json, logging
from aiocoap import Context, Message, resource, POST
import paho.mqtt.client as mqtt
import cbor2
from jsonschema import validate, ValidationError

BROKER = "mqtt.example.com"
MQTT_TOPIC = "factory/telemetry"
JSON_SCHEMA = {"type": "object", "properties": {"ts": {"type": "string"}, "temp": {"type": "number"}}, "required": ["ts","temp"]}

class CoAPResource(resource.Resource):
    def __init__(self, mqtt_client):
        super().__init__()
        self.mqtt = mqtt_client

    async def render_post(self, request):
        try:
            payload = cbor2.loads(request.payload)              # binary decode
            # mapping: normalize units and convert timestamp
            payload["temp"] = float(payload.get("raw_temp")/100.0)
            payload["ts"] = payload.get("ts_iso") or \
                            asyncio.get_event_loop().time().__str__()
            validate(payload, JSON_SCHEMA)                      # schema validation
            self.mqtt.publish(MQTT_TOPIC, json.dumps(payload), qos=1)  # ordered, at-least-once
            return Message(code=POST, payload=b"OK")
        except (cbor2.CBORDecodeError, ValidationError) as e:
            logging.warning("Payload error: %s", e)
            return Message(code=POST, payload=b"ERR")

def mqtt_connect_loop(client):
    while True:
        try:
            client.connect(BROKER, 1883, keepalive=60)
            client.loop_start()
            return
        except Exception:
            logging.exception("MQTT connect failed, retrying")
            asyncio.sleep(5)

async def main():
    mqtt_client = mqtt.Client()
    mqtt_connect_loop(mqtt_client)
    root = resource.Site()
    root.add_resource(['sensor'], CoAPResource(mqtt_client))
    context = await Context.create_server_context(root, bind=('::', 5683))
    await asyncio.get_running_loop().create_future()  # run forever

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())