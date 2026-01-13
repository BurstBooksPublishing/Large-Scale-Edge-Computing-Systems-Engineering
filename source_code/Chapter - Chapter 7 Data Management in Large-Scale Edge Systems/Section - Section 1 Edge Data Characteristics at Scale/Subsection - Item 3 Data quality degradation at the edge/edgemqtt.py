import time, json, sqlite3
import ntplib, paho.mqtt.client as mqtt
from prometheus_client import Gauge, start_http_server

# Prometheus metric
sensor_val = Gauge('edge_sensor_value', 'Smoothed sensor value', ['sensor_id'])

# Simple 1D Kalman filter
class Kalman1D:
    def __init__(self, q=1e-3, r=1e-2):
        self.q, self.r = q, r; self.x = None; self.p = 1.0
    def update(self, z):
        if self.x is None: self.x = z; return z
        # predict
        self.p += self.q
        # update
        k = self.p / (self.p + self.r)
        self.x += k * (z - self.x)
        self.p *= (1 - k)
        return self.x

# NTP offset (cached)
ntp_client = ntplib.NTPClient()
try:
    resp = ntp_client.request('pool.ntp.org', version=3, timeout=1)
    ntp_offset = resp.offset
except Exception:
    ntp_offset = 0.0

db = sqlite3.connect('/var/lib/edge/sensor_data.db')
db.execute('CREATE TABLE IF NOT EXISTS data(id TEXT, ts REAL, val REAL)')
kalman = {}

def on_message(_, __, msg):
    try:
        p = json.loads(msg.payload.decode())
        sid = p['sensor_id']; t = float(p['ts']); v = float(p['value'])
        # correct timestamp using NTP offset
        t += ntp_offset
        # basic validation
        if not (-2000 < v < 2000): return
        k = kalman.setdefault(sid, Kalman1D())
        sv = k.update(v)
        sensor_val.labels(sensor_id=sid).set(sv)
        db.execute('INSERT INTO data VALUES(?,?,?)', (sid, t, sv))
        db.commit()
    except Exception:
        # minimal logging; in production use structured logging and dead-letter queue
        pass

start_http_server(8000)  # Prometheus scrape endpoint
client = mqtt.Client()
client.on_message = on_message
client.connect('localhost', 1883, 60)
client.subscribe('sensors/+/vibration', qos=1)
client.loop_forever()