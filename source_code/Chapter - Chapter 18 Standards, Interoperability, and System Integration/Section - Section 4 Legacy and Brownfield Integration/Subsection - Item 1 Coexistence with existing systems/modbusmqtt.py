#!/usr/bin/env python3
# Poll Modbus RTU devices and publish to MQTT with batching, TLS, and backoff.
import time, json, logging
from typing import List
import minimalmodbus
import paho.mqtt.client as mqtt

LOG = logging.getLogger("modbus_mqtt")
logging.basicConfig(level=logging.INFO)

# Configuration (move to secure config in production)
MODBUS_PORT = "/dev/ttyUSB0"
BAUDRATE = 19200
MQTT_BROKER = "edge-broker.local"
MQTT_PORT = 8883
MQTT_TOPIC_PREFIX = "plant/line1"
TLS_CA = "/etc/ssl/certs/ca.pem"
POLL_INTERVAL_S = 1.0
BATCH_SIZE = 50

# Legacy device map: list of (unit_id, register_addr, length, topic_suffix)
DEVICES = [
    (1, 0, 2, "pump1"),
    (2, 0, 2, "valve3"),
    # ... add realistic mapping
]

# Setup Modbus instrument (single serial bus, slave ID varies per read)
modbus_instrument = minimalmodbus.Instrument(MODBUS_PORT, 1)
modbus_instrument.serial.baudrate = BAUDRATE
modbus_instrument.serial.timeout = 0.5
modbus_instrument.mode = minimalmodbus.MODE_RTU

# MQTT client with TLS and automatic reconnect
mqtt_client = mqtt.Client(client_id="modbus_gateway_line1")
mqtt_client.tls_set(ca_certs=TLS_CA)
mqtt_client.username_pw_set("gateway", "REPLACE_SECRET")  # use vault in prod
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=120)
mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT)
mqtt_client.loop_start()

def read_registers(unit_id: int, addr: int, count: int):
    modbus_instrument.address = unit_id
    try:
        # Read multiple registers (16-bit); production: validate CRC and scale
        vals = modbus_instrument.read_registers(addr, count, functioncode=3)
        return vals
    except IOError as e:
        LOG.warning("Modbus read failed unit %d addr %d: %s", unit_id, addr, e)
        return None

def publish_batch(messages: List[dict]):
    payload = json.dumps({"ts": int(time.time()*1000), "data": messages})
    mqtt_client.publish(f"{MQTT_TOPIC_PREFIX}/telemetry", payload, qos=1)

def main_loop():
    backoff = 1.0
    while True:
        batch = []
        start = time.time()
        for (unit, addr, length, suffix) in DEVICES:
            vals = read_registers(unit, addr, length)
            if vals is not None:
                batch.append({"device": suffix, "unit": unit, "values": vals})
                backoff = 1.0  # reset backoff on success
            if len(batch) >= BATCH_SIZE:
                publish_batch(batch); batch.clear()
        if batch:
            publish_batch(batch)
        elapsed = time.time() - start
        sleep_for = max(0, POLL_INTERVAL_S - elapsed)
        if sleep_for == 0:
            LOG.warning("Poll loop overran interval by %.3fs", elapsed - POLL_INTERVAL_S)
        time.sleep(sleep_for)
        # simple exponential backoff on repeated failures (implement circuit breaker if needed)

if __name__ == "__main__":
    try:
        main_loop()
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()