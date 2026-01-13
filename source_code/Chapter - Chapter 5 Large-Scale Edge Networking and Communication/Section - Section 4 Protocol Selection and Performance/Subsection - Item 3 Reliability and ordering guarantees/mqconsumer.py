import sqlite3, json, time
import paho.mqtt.client as mqtt

DB_PATH = "/var/lib/edge_agg/state.db"
MQTT_BROKER = "127.0.0.1"
TOPIC = "telemetry/#"

# durable DB init (ensure WAL for concurrency, fsync on commit).
def init_db():
    conn = sqlite3.connect(DB_PATH, isolation_level="EXCLUSIVE", timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""CREATE TABLE IF NOT EXISTS last_seq (
                        producer TEXT PRIMARY KEY,
                        seq INTEGER NOT NULL
                    );""")
    conn.commit()
    return conn

conn = init_db()

def accept_message(producer: str, seq: int) -> bool:
    # returns True if message is new and accepted in order
    cur = conn.cursor()
    cur.execute("SELECT seq FROM last_seq WHERE producer = ?;", (producer,))
    row = cur.fetchone()
    if row is None:
        # insert first-seen sequence; durable commit
        cur.execute("INSERT INTO last_seq(producer, seq) VALUES(?,?);", (producer, seq))
        conn.commit()
        return True
    last = row[0]
    if seq <= last:
        return False  # duplicate or out-of-order older
    # allow only monotonic increase; for gaps, could buffer or request retransmit
    cur.execute("UPDATE last_seq SET seq = ? WHERE producer = ?;", (seq, producer))
    conn.commit()
    return True

def on_message(client, userdata, msg):
    # minimal validation and ordering
    payload = json.loads(msg.payload.decode())
    producer = payload["device_id"]
    seq = int(payload["seq"])
    if accept_message(producer, seq):
        process(payload)  # application-specific, idempotent
    else:
        # drop duplicate/old; logging for diagnostics
        pass

def process(payload):
    # placeholder: lightweight, idempotent processing
    # ensure downstream at-least-once semantics or transactional write
    print("Processed", payload["device_id"], payload["seq"])

client = mqtt.Client(client_id="edge_aggregator")
client.on_message = on_message
client.connect(MQTT_BROKER)
client.subscribe(TOPIC, qos=1)
client.loop_forever()