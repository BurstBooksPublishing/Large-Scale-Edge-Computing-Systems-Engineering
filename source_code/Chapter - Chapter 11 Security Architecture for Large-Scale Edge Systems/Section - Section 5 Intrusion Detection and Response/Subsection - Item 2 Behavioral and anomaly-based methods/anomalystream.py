import time, json, math, socket
import numpy as np
import paho.mqtt.client as mqtt

# Online mean/cov estimator (Welford for mean, incremental cov)
class OnlineCov:
    def __init__(self, dim):
        self.n = 0
        self.mean = np.zeros(dim)
        self.M2 = np.zeros((dim, dim))
    def update(self, x):
        self.n += 1
        delta = x - self.mean
        self.mean += delta / self.n
        delta2 = x - self.mean
        self.M2 += np.outer(delta, delta2)
    def cov(self):
        return self.M2 / (self.n - 1) if self.n > 1 else np.eye(len(self.mean))*1e-6

# Mahalanobis score with regularization for numerical stability
def maha_score(x, mean, cov, reg=1e-6):
    cov_reg = cov + np.eye(cov.shape[0])*reg
    L = np.linalg.cholesky(cov_reg)
    y = np.linalg.solve(L, x - mean)
    return float(np.dot(y, y))

# MQTT alert publisher (optional)
def publish_alert(mqtt_client, topic, payload):
    mqtt_client.publish(topic, json.dumps(payload), qos=1)

# Initialize
DIM = 3
est = OnlineCov(DIM)
mqttc = mqtt.Client()
mqttc.connect("edge-broker.local", 1883, 60)
ALERT_TOPIC = "edge/alerts/anomaly"
THRESHOLD = 9.21  # chi-square 95% for df=3 as an initial heuristic

# Streaming loop: replace get_sensor_vector with actual sensor read
def get_sensor_vector():
    # placeholder: real code reads ADC, CAN, I2C sensors
    return np.array([read_rms(), read_current(), read_temp()])

while True:
    x = get_sensor_vector()
    est.update(x)
    if est.n > DIM+1:
        s = maha_score(x, est.mean, est.cov())
        # EWMA smoothing of scores could be added here
        if s > THRESHOLD:
            payload = {"ts": time.time(), "score": s, "mean": est.mean.tolist()}
            publish_alert(mqttc, ALERT_TOPIC, payload)
    time.sleep(1)  # maintain required sampling interval