import sqlite3, json, uuid, time, requests
import paho.mqtt.client as mqtt

DB_PATH = "/var/lib/edge/dedup.db"
API_URL = "https://cloud.example/api/events/"

# initialize durable dedup table
conn = sqlite3.connect(DB_PATH, isolation_level="EXCLUSIVE", timeout=30)
conn.execute("CREATE TABLE IF NOT EXISTS processed(id TEXT PRIMARY KEY, ts INTEGER)")
conn.commit()

def mark_processed(tx, event_id):
    # Durable insert; will fail on duplicates
    tx.execute("INSERT INTO processed(id, ts) VALUES (?, ?)", (event_id, int(time.time())))

def already_processed(tx, event_id):
    cur = tx.execute("SELECT 1 FROM processed WHERE id = ? LIMIT 1", (event_id,))
    return cur.fetchone() is not None

def forward_event(payload, event_id):
    # idempotent PUT: server must treat event_id as idempotency key
    r = requests.put(API_URL + event_id, json=payload, timeout=5)
    r.raise_for_status()

def on_message(client, userdata, msg):
    # parse event and ensure id exists
    obj = json.loads(msg.payload.decode())
    event_id = obj.get("id") or str(uuid.uuid1())
    payload = obj.get("payload", obj)

    try:
        with conn:  # sqlite transaction ensures atomicity of dedup mark
            if already_processed(conn, event_id):
                return  # duplicate; ignore
            forward_event(payload, event_id)  # may raise on network error
            mark_processed(conn, event_id)    # durable commit happens only after successful forward
    except Exception as e:
        # transient failures: rely on MQTT at-least-once redelivery and retry later
        client.reconnect()

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883)
client.subscribe("sensors/vibration")
client.loop_forever()