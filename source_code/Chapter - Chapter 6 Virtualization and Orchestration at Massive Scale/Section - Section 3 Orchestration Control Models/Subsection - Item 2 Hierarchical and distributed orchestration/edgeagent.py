#!/usr/bin/env python3
"""
Production-ready edge aggregator:
- subscribes to local telemetry topics
- windowed aggregation (count, mean, max)
- publishes summarized JSON to upstream broker with TLS and backoff
"""
import os
import asyncio
import json
import ssl
from datetime import datetime, timezone
from collections import defaultdict
import asyncio_mqtt as aiomqtt  # install: pip install asyncio-mqtt

BROKER = os.getenv("UPSTREAM_BROKER", "upstream.example.com")
BROKER_PORT = int(os.getenv("UPSTREAM_PORT", "8883"))
TLS_CA = os.getenv("TLS_CA", "/etc/ssl/ca.pem")
TLS_CERT = os.getenv("TLS_CERT", "/etc/ssl/cert.pem")
TLS_KEY = os.getenv("TLS_KEY", "/etc/ssl/key.pem")
AGG_WINDOW = float(os.getenv("AGG_WINDOW", "5.0"))  # seconds
LOCAL_TOPIC = os.getenv("LOCAL_TOPIC", "devices/+/telemetry")
OUT_TOPIC = os.getenv("OUT_TOPIC", "site/summary")

ssl_ctx = ssl.create_default_context(cafile=TLS_CA)
ssl_ctx.load_cert_chain(certfile=TLS_CERT, keyfile=TLS_KEY)

async def aggregate_loop(client):
    buf = defaultdict(list)
    last_emit = asyncio.get_event_loop().time()
    async with aiomqtt.Client(BROKER, port=BROKER_PORT, tls=ssl_ctx) as mqtt:
        # subscribe to all local telemetry (assumes local broker bridges messages)
        await mqtt.subscribe(LOCAL_TOPIC)
        async with mqtt.unfiltered_messages() as messages:
            async for msg in messages:
                try:
                    payload = json.loads(msg.payload.decode())
                except Exception:
                    continue  # drop malformed
                key = payload.get("sensor_id", "unknown")
                value = float(payload.get("value", 0.0))
                buf[key].append(value)
                now = asyncio.get_event_loop().time()
                if now - last_emit >= AGG_WINDOW:
                    summary = {"ts": datetime.now(timezone.utc).isoformat(), "site": os.getenv("SITE_ID","site-1"), "metrics": {}}
                    for k, vals in buf.items():
                        summary["metrics"][k] = {"count": len(vals), "mean": sum(vals)/len(vals), "max": max(vals)}
                    await publish_with_backoff(mqtt, OUT_TOPIC, json.dumps(summary).encode())
                    buf.clear()
                    last_emit = now

async def publish_with_backoff(mqtt, topic, payload):
    backoff = 0.5
    while True:
        try:
            await mqtt.publish(topic, payload, qos=1)
            return
        except aiomqtt.MqttError:
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30.0)  # cap backoff

def main():
    asyncio.run(aggregate_loop(None))

if __name__ == "__main__":
    main()