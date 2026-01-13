import time
import threading
import struct
import queue
import json
import paho.mqtt.client as mqtt

class SensorAggregator:
    def __init__(self, read_sample, mqtt_config, window_s=0.1, rms_threshold=0.5, buffer_file="buffer.bin"):
        self.read_sample = read_sample                      # pluggable sensor read() -> float
        self.window_s = window_s
        self.rms_threshold = rms_threshold
        self.mqtt_cfg = mqtt_config
        self.client = mqtt.Client(client_id=mqtt_config.get("client_id"))
        self.client.username_pw_set(mqtt_config.get("user"), mqtt_config.get("pass"))
        self.client.will_set(mqtt_config.get("topic"), json.dumps({"status":"offline"}), qos=1, retain=True)
        self.buffer = queue.Queue()
        self.buffer_file = buffer_file
        self._stop = threading.Event()
        self._connect()

    def _connect(self):
        # start network loop in background thread for asynchronous publish
        self.client.connect(self.mqtt_cfg["host"], self.mqtt_cfg.get("port",1883))
        self.client.loop_start()
        # attempt to replay persisted buffer on startup
        try:
            with open(self.buffer_file, "rb") as f:
                while True:
                    size_bytes = f.read(4)
                    if not size_bytes: break
                    sz = struct.unpack(">I", size_bytes)[0]
                    payload = f.read(sz)
                    self.client.publish(self.mqtt_cfg["topic"], payload)
        except FileNotFoundError:
            pass

    def _persist_buffered(self):
        # persist queue to file to survive reboots and network outages
        items = []
        while not self.buffer.empty():
            items.append(self.buffer.get())
        with open(self.buffer_file, "wb") as f:
            for p in items:
                f.write(struct.pack(">I", len(p)))
                f.write(p)
        # restore in-memory queue
        for p in items:
            self.buffer.put(p)

    def run(self):
        # main loop: windowed RMS computation
        samples = []
        start = time.time()
        try:
            while not self._stop.is_set():
                samples.append(self.read_sample())
                now = time.time()
                if now - start >= self.window_s:
                    rms = (sum(x*x for x in samples)/len(samples))**0.5
                    payload = json.dumps({"ts": int(now*1000), "rms": rms}).encode()
                    if rms >= self.rms_threshold:
                        info = self.client.publish(self.mqtt_cfg["topic"], payload, qos=1)
                        if info.rc != mqtt.MQTT_ERR_SUCCESS:
                            # enqueue when publish failed
                            self.buffer.put(payload)
                            self._persist_buffered()
                    samples.clear()
                    start = now
        finally:
            self.client.loop_stop()
            self.client.disconnect()

    def stop(self):
        self._stop.set()

# Example pluggable reader for production: replace with ADC library call (e.g., spidev, iio)
def dummy_reader():
    import math, random
    t = time.time()
    return 0.1*math.sin(2*math.pi*100*t) + 0.01*random.gauss(0,1)

# MQTT config example
mqtt_cfg = {"host":"mqtt.local","topic":"site/line1/bearing","client_id":"agg01","user":"iot","pass":"s3cret"}
agg = SensorAggregator(dummy_reader, mqtt_cfg, window_s=0.1, rms_threshold=0.02)
thread = threading.Thread(target=agg.run, daemon=True)
thread.start()
# graceful shutdown handled by operator/OS signals in production