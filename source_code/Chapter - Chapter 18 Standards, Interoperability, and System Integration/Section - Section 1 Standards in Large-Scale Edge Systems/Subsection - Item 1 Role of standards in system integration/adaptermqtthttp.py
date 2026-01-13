import asyncio
import jsonschema
import aiohttp
from asyncio_mqtt import Client, MqttError

SCHEMA = {"type": "object", "properties": {"device": {"type": "string"}, "ts": {"type": "number"}, "metrics": {"type": "object"}}, "required": ["device","ts","metrics"]}
MQTT_BROKER = "mqtt.example.local"
MQTT_TOPIC = "edge/telemetry"
HTTP_INGEST = "https://ingest.example.com/v1/telemetry"

async def publish_http(session, payload):
    # idempotent POST with retry on transient errors
    for backoff in (1,2,4):
        try:
            async with session.post(HTTP_INGEST, json=payload, timeout=5) as resp:
                resp.raise_for_status()
                return await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await asyncio.sleep(backoff)
    raise RuntimeError("HTTP publish failed")

async def mqtt_publisher(queue):
    # resilient MQTT publisher
    while True:
        try:
            async with Client(MQTT_BROKER) as client:
                while True:
                    payload = await queue.get()
                    await client.publish(MQTT_TOPIC, payload)
                    queue.task_done()
        except MqttError:
            await asyncio.sleep(2)  # reconnect backoff

async def normalize_and_route(raw_source, queue, session):
    # parse, validate, normalize, and enqueue for MQTT and HTTP
    payload = jsonschema.validate(json.loads(raw_source), SCHEMA) if isinstance(raw_source, str) else jsonschema.validate(raw_source, SCHEMA)
    # ensure canonical timestamp and minimal fields
    normalized = {"device": payload["device"], "ts": float(payload["ts"]), "metrics": payload["metrics"]}
    await queue.put(json.dumps(normalized))
    await publish_http(session, normalized)

async def main():
    queue = asyncio.Queue(maxsize=1000)
    async with aiohttp.ClientSession() as session:
        mqtt_task = asyncio.create_task(mqtt_publisher(queue))
        # Example: process incoming messages from message queue or socket
        # Here we simulate with a simple loop reading from stdin
        loop = asyncio.get_event_loop()
        while True:
            raw = await loop.run_in_executor(None, input)
            asyncio.create_task(normalize_and_route(raw, queue, session))

if __name__ == "__main__":
    asyncio.run(main())