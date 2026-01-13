#!/usr/bin/env python3
# Simple rotation coordinator: schedules rotations and publishes signed commands.
import sqlite3, time, hmac, hashlib, json, ssl
import paho.mqtt.client as mqtt

DB = 'km_state.db'
MQTT_BROKER = 'mqtt.example.internal'
MQTT_PORT = 8883
ROOT_KEY = b'supersecret-signing-key'  # use HSM in production

# initialize DB
with sqlite3.connect(DB) as db:
    db.execute('CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY,last_rot_ts INTEGER)')
    db.commit()

def sign_command(payload: bytes) -> str:
    # HMAC over payload; replace with asymmetric signature when available.
    return hmac.new(ROOT_KEY, payload, hashlib.sha256).hexdigest()

def schedule_and_publish(client, device_id, rotate_ts):
    cmd = {'cmd':'rotate','ts': rotate_ts}
    payload = json.dumps(cmd).encode('utf-8')
    sig = sign_command(payload)
    topic = f'devices/{device_id}/commands/rotate'
    msg = json.dumps({'payload':cmd,'sig':sig})
    client.publish(topic, msg, qos=1)  # broker enforces TLS+auth

def main_loop():
    # TLS context; use client certificates in production.
    tls = {'ca_certs':'/etc/ssl/certs/ca.pem'}
    client = mqtt.Client()
    client.tls_set(ca_certs=tls['ca_certs'], certfile=None, keyfile=None,
                   cert_reqs=ssl.CERT_REQUIRED)
    client.username_pw_set('orchestrator', password=None)  # broker auth
    client.connect(MQTT_BROKER, MQTT_PORT)
    client.loop_start()

    while True:
        now = int(time.time())
        with sqlite3.connect(DB) as db:
            for row in db.execute('SELECT device_id,last_rot_ts FROM devices'):
                device_id, last = row
                # rotation policy: rotate every 180 days
                if now - last > 180*24*3600:
                    schedule_and_publish(client, device_id, now)
                    db.execute('UPDATE devices SET last_rot_ts=? WHERE device_id=?',(now,device_id))
            db.commit()
        time.sleep(60)

if __name__=='__main__':
    main_loop()