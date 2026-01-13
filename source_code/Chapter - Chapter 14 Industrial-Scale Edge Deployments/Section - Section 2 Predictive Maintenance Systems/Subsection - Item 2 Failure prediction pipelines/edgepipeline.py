#!/usr/bin/env python3
# Production-ready edge pipeline: features -> TFLite inference -> secure MQTT alert
import time, ssl, json, numpy as np
import paho.mqtt.client as mqtt
from tflite_runtime.interpreter import Interpreter  # lightweight runtime

MODEL_PATH = "/opt/models/spindle_detector.tflite"
MQTT_HOST = "iot-gateway.example.com"
MQTT_PORT = 8883
TOPIC_ALERT = "factory/line1/spindle/alerts"
SENSOR_WINDOW = 256  # samples per inference
SAMPLE_RATE = 8000   # Hz

# Initialize interpreter (delegate CPU/GPU as available)
interp = Interpreter(MODEL_PATH)
interp.allocate_tensors()
input_index = interp.get_input_details()[0]['index']
output_index = interp.get_output_details()[0]['index']

# Secure MQTT client configuration
client = mqtt.Client(client_id="node-123")
client.tls_set(ca_certs="/etc/ssl/ca.pem", certfile="/etc/ssl/cert.pem",
               keyfile="/etc/ssl/key.pem", tls_version=ssl.PROTOCOL_TLSv1_2)
client.username_pw_set("edge_device", "secure_token")
client.connect_async(MQTT_HOST, MQTT_PORT)
client.loop_start()

def extract_features(samples: np.ndarray) -> np.ndarray:
    # compute normalized RMS, spectral centroid, spectral kurtosis
    rms = np.sqrt(np.mean(samples**2))
    spec = np.abs(np.fft.rfft(samples))
    norm = spec / (np.sum(spec)+1e-9)
    centroid = np.sum(np.arange(norm.size)*norm)
    kurt = np.mean((samples - samples.mean())**4) / (samples.var()+1e-9)**2
    return np.array([rms, centroid, kurt], dtype=np.float32)

def run_inference(feat: np.ndarray) -> float:
    # feature vector -> model probability
    interp.set_tensor(input_index, feat.reshape(1, -1))
    interp.invoke()
    out = interp.get_tensor(output_index)
    return float(out[0,0])

def publish_alert(payload: dict):
    # JSON payload with event timestamp and risk score
    backoff = 1.0
    while True:
        try:
            client.publish(TOPIC_ALERT, json.dumps(payload), qos=1)
            return
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff*2, 60.0)

# Main loop: local sampler replaced with real ADC driver in production
buffer = np.zeros(SENSOR_WINDOW, dtype=np.float32)
while True:
    # replace synthetic sample generation with ADC reads or IIO API
    buffer = np.random.normal(0, 1, size=SENSOR_WINDOW).astype(np.float32)
    feat = extract_features(buffer)
    p = run_inference(feat)
    if p >= 0.7:  # operational threshold
        payload = {"timestamp": time.time(), "risk": p, "node": "node-123"}
        publish_alert(payload)
    time.sleep(SENSOR_WINDOW / SAMPLE_RATE)  # maintain sampling cadence