#!/usr/bin/env python3
# Edge aggregator: polls sensors, computes features, publishes via MQTT over TLS.

import asyncio
import ssl
import struct
import json
import time
import numpy as np
import paho.mqtt.client as mqtt

# Configuration (externalize in production)
BROKER='broker.example.com'
BROKER_PORT=8883
TLS_CERT='/etc/ssl/certs/edge-client.pem'
CLIENT_ID='edge-node-01'
POLL_INTERVAL=0.2  # seconds
SAMPLE_WINDOW=512  # samples for FFT
SENSOR_ENDPOINTS=[('192.168.10.10', 502), ('192.168.10.11', 502)]  # Modbus/TCP devices

# Minimal resilient MQTT wrapper
def mqtt_client():
    client = mqtt.Client(client_id=CLIENT_ID)
    client.tls_set(ca_certs=None, certfile=TLS_CERT, cert_reqs=ssl.CERT_REQUIRED)
    client.tls_insecure_set(False)
    client.connect_async(BROKER, BROKER_PORT)
    client.loop_start()
    return client

# Placeholder: read raw samples from networked sensor (replace with industrial lib)
async def read_sensor_stream(addr, port, n):
    await asyncio.sleep(0)  # non-blocking
    # Simulate n samples of vibration (replace with Modbus/CoAP read)
    t = np.linspace(0, n/5000, n, endpoint=False)
    data = 0.1*np.sin(2*np.pi*120*t) + 0.01*np.random.randn(n)
    return data.astype(np.float32)

# Feature computation: RMS and top-3 FFT peaks
def compute_features(samples, fs=5000):
    rms = float(np.sqrt(np.mean(samples**2)))
    fft = np.fft.rfft(samples * np.hanning(len(samples)))
    mags = np.abs(fft)
    freqs = np.fft.rfftfreq(len(samples), 1/fs)
    peak_idx = np.argsort(mags)[-3:][::-1]
    peaks = [{'f': float(freqs[i]), 'mag': float(mags[i])} for i in peak_idx]
    return {'rms': rms, 'peaks': peaks, 'ts': time.time()}

async def poll_and_publish(mqttc):
    while True:
        tasks = [read_sensor_stream(ip, port, SAMPLE_WINDOW) for ip, port in SENSOR_ENDPOINTS]
        streams = await asyncio.gather(*tasks, return_exceptions=False)
        for idx, samples in enumerate(streams):
            features = compute_features(samples)
            topic = f'edge/{CLIENT_ID}/sensor/{idx}/features'
            payload = json.dumps(features, separators=(',',':')).encode('utf-8')
            # Publish with QoS 1 and local buffering in broker; include LWT in production
            mqttc.publish(topic, payload, qos=1)
        await asyncio.sleep(POLL_INTERVAL)

def main():
    mqttc = mqtt_client()
    try:
        asyncio.run(poll_and_publish(mqttc))
    except KeyboardInterrupt:
        pass
    finally:
        mqttc.loop_stop()
        mqttc.disconnect()

if __name__ == '__main__':
    main()