#!/usr/bin/env python3
# Minimal, production-ready risk scorer using paho-mqtt and JSON config.
import json, ssl, time, logging
import statistics
import paho.mqtt.client as mqtt

# Load asset values and hazard rates from file
with open('/etc/edge/risk_config.json') as f:
    cfg = json.load(f)

BROKER = cfg['mqtt']['broker']
PORT = cfg['mqtt'].get('port', 8883)
TOPIC_TELEMETRY = cfg['topics']['telemetry']
TOPIC_ALERT = cfg['topics']['alerts']
CLIENT_ID = cfg.get('client_id','risk-agent')

logging.basicConfig(level=logging.INFO)
buffer = {}  # per-event sliding windows

def compute_expected_loss(window, hazard_rate, impact):
    # window: recent exposure times in seconds
    avg_exposure = statistics.mean(window) if window else 0.0
    return hazard_rate * impact * avg_exposure

def on_connect(client, userdata, flags, rc):
    client.subscribe(TOPIC_TELEMETRY)
    logging.info('connected to broker rc=%s', rc)

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    # payload contains: event_id, latency, confidence, timestamp
    eid = payload['event_id']
    buf = buffer.setdefault(eid, [])
    buf.append(payload['latency'])
    if len(buf) > 50: buf.pop(0)  # keep small sliding window

    cfg_item = cfg['events'].get(eid)
    if not cfg_item: return

    expected = compute_expected_loss(buf, cfg_item['hazard_rate'], cfg_item['impact'])
    if expected > cfg_item['threshold']:
        alert = {'event_id': eid, 'risk': expected, 'ts': time.time()}
        client.publish(TOPIC_ALERT, json.dumps(alert), qos=1)
        logging.warning('alert published %s', alert)

client = mqtt.Client(client_id=CLIENT_ID)
client.tls_set(ca_certs='/etc/ssl/ca.pem', certfile='/etc/ssl/cert.pem',
               keyfile='/etc/ssl/key.pem', tls_version=ssl.PROTOCOL_TLSv1_2)
client.tls_insecure_set(False)
client.on_connect = on_connect
client.on_message = on_message

while True:
    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever()
    except Exception as e:
        logging.error('mqtt connection error: %s', e)
        time.sleep(5)  # backoff and retry