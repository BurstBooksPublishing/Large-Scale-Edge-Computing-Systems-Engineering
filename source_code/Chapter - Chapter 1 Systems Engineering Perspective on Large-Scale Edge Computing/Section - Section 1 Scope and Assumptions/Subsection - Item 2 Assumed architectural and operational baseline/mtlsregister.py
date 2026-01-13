#!/usr/bin/env python3
# Production-ready: robust reconnects, TLS verification, JSON capability payload.
import ssl, json, socket
import paho.mqtt.client as mqtt

BROKER = "mqtt-broker.local"          # replace with broker DNS/IP
PORT = 8883
CLIENT_ID = "edge-device-001"
CA_CERT = "/etc/pki/ca.crt"
CLIENT_CERT = "/etc/pki/device.crt"
CLIENT_KEY = "/etc/pki/device.key"
TOPIC_REG = "devices/registration"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        # publish retained registration for operator/registry consumption
        payload = json.dumps({
            "id": CLIENT_ID,
            "hw": {"soc":"jetson_xavier", "ram_mb":8192},
            "sw": {"os":"ubuntu-20.04", "rt_kernel":False},
            "capabilities": ["local_inference","ota","ptp"]
        })
        client.publish(TOPIC_REG, payload, qos=1, retain=True)

def make_mqtt_client():
    client = mqtt.Client(client_id=CLIENT_ID, clean_session=False)
    client.tls_set(ca_certs=CA_CERT,
                   certfile=CLIENT_CERT,
                   keyfile=CLIENT_KEY,
                   cert_reqs=ssl.CERT_REQUIRED,
                   tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.tls_insecure_set(False)
    client.on_connect = on_connect
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    return client

def main():
    client = make_mqtt_client()
    client.connect(BROKER, PORT, keepalive=60)
    client.loop_start()
    try:
        while True:
            # periodic heartbeat for liveness and simple health checks
            client.publish(f"devices/{CLIENT_ID}/heartbeat", "ok", qos=1)
            socket.sleep(30)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()