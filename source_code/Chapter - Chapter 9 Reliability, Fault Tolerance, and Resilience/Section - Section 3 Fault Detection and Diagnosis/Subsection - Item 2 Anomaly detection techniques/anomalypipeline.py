#!/usr/bin/env python3
# Minimal production pattern: batching, quantized TFLite inference, persistent model loading.

import os, json, time, numpy as np
import paho.mqtt.client as mqtt
from sklearn.ensemble import IsolationForest
import joblib
import tflite_runtime.interpreter as tflite

# Load IsolationForest (pre-trained, saved with joblib)
IF_MODEL_PATH = "/opt/models/isolation_forest.joblib"
if_model = joblib.load(IF_MODEL_PATH)

# Load TFLite autoencoder (quantized)
AE_MODEL_PATH = "/opt/models/autoencoder.tflite"
interpreter = tflite.Interpreter(model_path=AE_MODEL_PATH)
interpreter.allocate_tensors()
input_index = interpreter.get_input_details()[0]['index']
output_index = interpreter.get_output_details()[0]['index']

# MQTT publisher configuration (use mTLS in production)
MQTT_BROKER = "edge-broker.local"
client = mqtt.Client()
client.connect(MQTT_BROKER, 1883, 60)

# Thresholds and fusion weights (tuned offline)
W_RECON, W_IF = 0.6, 0.4
FUSION_THRESHOLD = 0.7

def tflite_reconstruction_error(feature: np.ndarray) -> float:
    # Single-sample inference; features shape (n,)
    inp = np.expand_dims(feature.astype(np.float32), axis=0)
    interpreter.set_tensor(input_index, inp)
    interpreter.invoke()
    out = interpreter.get_tensor(output_index)
    # Mean squared error normalized by feature scale
    return float(np.mean((inp - out)**2))

def isolation_score(feature: np.ndarray) -> float:
    # sklearn outputs negative scores for normal; convert to [0,1]
    raw = if_model.decision_function(feature.reshape(1, -1))[0]
    return float(1.0 / (1.0 + np.exp(-raw)))  # sigmoid mapping

def publish_anomaly(feature, score, meta):
    payload = json.dumps({"ts": time.time(), "score": score, "meta": meta})
    client.publish("anomaly/edge", payload, qos=1)

# Main loop: consume features from local ingress (replace with real ingestion)
def process_batch(batch_features):
    for f in batch_features:
        r = tflite_reconstruction_error(f)
        i = isolation_score(f)
        norm_r = r / (r + 1e-6)  # simple normalization
        score = W_RECON * norm_r + W_IF * i
        if score > FUSION_THRESHOLD:
            publish_anomaly(f.tolist(), score, {"node":"edge-01"})

# Example usage: replace with real stream reader
if __name__ == "__main__":
    while True:
        # read_features() should return list of np.ndarray feature vectors
        batch = read_features()  # implement sensor ingestion separately
        process_batch(batch)
        time.sleep(0.1)  # control CPU usage