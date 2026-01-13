#!/usr/bin/env python3
import time, json, gzip, socket
import psutil, requests, queue, threading
import paho.mqtt.client as mqtt

EXPORT_INTERVAL = 5.0  # seconds
MAX_BATCH_BYTES = 64*1024  # bytes
BANDWIDTH_WINDOW = 30.0  # seconds

# telemetry queue (thread-safe)
txq = queue.Queue(maxsize=1000)

def collect_metrics():
    # small, cheap probes suitable for constrained SoCs
    m = {
        "ts": time.time(),
        "cpu": psutil.cpu_percent(interval=None),
        "mem_pct": psutil.virtual_memory().percent,
        "net_bytes": psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
    }
    return m

def exporter_worker(http_endpoint, mqtt_broker):
    mqttc = mqtt.Client()
    mqttc.connect(mqtt_broker, 1883, 10)
    last_net = None
    window_bytes = []
    while True:
        batch = []
        size = 0
        # build batch up to MAX_BATCH_BYTES or EXPORT_INTERVAL
        start = time.time()
        while time.time() - start < EXPORT_INTERVAL and size < MAX_BATCH_BYTES:
            try:
                item = txq.get(timeout=EXPORT_INTERVAL - (time.time()-start))
            except queue.Empty:
                break
            s = json.dumps(item).encode("utf-8")
            batch.append(s)
            size += len(s)
        if not batch:
            continue
        payload = b"\n".join(batch)
        comp = gzip.compress(payload)
        # try HTTP post first, fallback to MQTT
        try:
            r = requests.post(http_endpoint, data=comp,
                              headers={"Content-Encoding":"gzip","Content-Type":"application/json"},
                              timeout=5)
            r.raise_for_status()
        except Exception:
            # best-effort publish to local broker (gateway will forward)
            try:
                mqttc.publish("edge/telemetry", comp, qos=1)
            except Exception:
                # final fallback: drop oldest to avoid blocking critical tasks
                pass

def controller(adapt_rate):
    # simple adaptive logic using CPU and recent net usage
    history = []
    while True:
        cpu = psutil.cpu_percent(interval=1)
        net = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
        history.append((time.time(), cpu, net))
        # compute bandwidth estimate over window
        cutoff = time.time() - BANDWIDTH_WINDOW
        while history and history[0][0] < cutoff:
            history.pop(0)
        if len(history) >= 2:
            delta_bytes = history[-1][2] - history[0][2]
            bw = delta_bytes / BANDWIDTH_WINDOW
        else:
            bw = 0.0
        # adjust sampling frequency inversely with CPU and bandwidth usage
        freq = max(0.1, min(2.0, 1.0 - cpu/100.0 + (1000.0 - bw)/10000.0))
        adapt_rate['interval'] = 1.0 / freq
        time.sleep(1)

if __name__ == "__main__":
    http_endpoint = "https://collector.example.com/ingest"
    mqtt_broker = "gateway.local"
    adapt_rate = {"interval": 1.0}
    # start exporter thread
    threading.Thread(target=exporter_worker, args=(http_endpoint, mqtt_broker), daemon=True).start()
    threading.Thread(target=controller, args=(adapt_rate,), daemon=True).start()
    # main collection loop respects adaptive interval
    while True:
        txq.put_nowait(collect_metrics())
        time.sleep(adapt_rate['interval'])