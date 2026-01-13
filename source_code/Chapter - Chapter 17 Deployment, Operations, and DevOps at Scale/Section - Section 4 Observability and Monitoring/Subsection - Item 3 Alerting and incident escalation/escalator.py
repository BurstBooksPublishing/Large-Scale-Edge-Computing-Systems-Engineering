#!/usr/bin/env python3
import os, asyncio, hmac, hashlib, json, time
from aiohttp import web, ClientSession

# Config via env vars for safe deployment
PAGERDUTY_KEY = os.environ.get("PAGERDUTY_KEY")
ALERT_SECRET = os.environ.get("ALERT_SECRET","")  # HMAC secret from Alertmanager
MQTT_BROKER = os.environ.get("MQTT_BROKER","mqtt://localhost:1883")
DEDUP_WINDOW = float(os.environ.get("DEDUP_WINDOW","30.0"))  # seconds

# in-memory dedupe cache (bounded by design)
dedupe = {}  # key -> last_timestamp

async def send_pagerduty(session, payload):
    hdr = {"Content-Type":"application/json"}
    body = {"routing_key": PAGERDUTY_KEY, "event_action":"trigger", "payload": payload}
    async with session.post("https://events.pagerduty.com/v2/enqueue", json=body, headers=hdr, timeout=10) as r:
        r.raise_for_status()
        return await r.json()

async def publish_mqtt_remediate(topic, message):
    # lightweight MQTT publish using system mosquitto_pub for reliability on edge nodes
    # system must run mosquitto-clients; this avoids embedding MQTT libs for constrained fleets
    proc = await asyncio.create_subprocess_exec(
        "mosquitto_pub","-t", topic, "-m", json.dumps(message),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
    )
    await proc.wait()

def valid_hmac(body: bytes, signature: str) -> bool:
    if not ALERT_SECRET: return True
    mac = hmac.new(ALERT_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)

async def handle_alert(request):
    body = await request.read()
    sig = request.headers.get("X-Alert-Signature","")
    if not valid_hmac(body, sig):
        return web.Response(status=401, text="invalid signature")
    data = json.loads(body)
    now = time.time()
    tasks = []
    async with ClientSession() as session:
        for a in data.get("alerts",[]):
            # compute a stable dedupe key
            key = f"{a.get('labels',{}).get('device')}-{a.get('labels',{}).get('alertname')}"
            last = dedupe.get(key, 0)
            if now - last < DEDUP_WINDOW:
                continue  # suppressed
            dedupe[key] = now
            severity = a.get("labels",{}).get("severity","warning")
            # local remediation for critical and latency-sensitive alerts
            if severity in ("critical","fatal") and a.get("annotations",{}).get("auto_remediate","false")=="true":
                topic = f"edge/{a['labels'].get('device')}/remediate"
                tasks.append(publish_mqtt_remediate(topic, {"action":"isolate","alert":a}))
            # escalate to PagerDuty for human follow-up
            pd_payload = {"summary": a.get("annotations",{}).get("summary","alert"), "source": a.get("labels",{}).get("device")}
            tasks.append(send_pagerduty(session, pd_payload))
        # await all network tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
    return web.json_response({"status":"ok","results":[str(type(r)) for r in results]})

app = web.Application()
app.router.add_post("/webhook", handle_alert)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT","8080")))