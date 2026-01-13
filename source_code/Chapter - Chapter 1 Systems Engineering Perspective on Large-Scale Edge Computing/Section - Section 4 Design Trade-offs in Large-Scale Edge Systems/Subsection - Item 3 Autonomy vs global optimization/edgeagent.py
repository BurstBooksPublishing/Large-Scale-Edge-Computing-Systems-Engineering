import time, json, ssl, threading
import paho.mqtt.client as mqtt
import onnxruntime as ort

# Config (production: load from secure store)
MQTT_BROKER = "broker.example.com"
MQTT_PORT = 8883
TOPIC_STATE = "edge/agent_state"               # use \lstinline|edge/agent_state|
TOPIC_POLICY = "edge/policy/agent_group"
MODEL_PATH = "/opt/models/inspection.onnx"

sess = ort.InferenceSession(MODEL_PATH)        # ONNX Runtime inference session

def infer(frame):
    # Preprocess frame to input tensor; production code uses DMA buffers
    inp = preprocess(frame)
    out = sess.run(None, {"input": inp})
    return postprocess(out)

client = mqtt.Client()
client.tls_set(cert_reqs=ssl.CERT_REQUIRED)    # require server cert; add client certs for mTLS
client.username_pw_set("device-id", "token")   # better: use token from secure element

policy = {"lambda": 0.1, "threshold": 0.5}     # default policy

def on_message(_client, _userdata, msg):
    global policy
    try:
        policy = json.loads(msg.payload.decode())
    except Exception:
        pass  # ignore malformed

client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
client.subscribe(TOPIC_POLICY)
client.loop_start()

def telemetry_loop():
    while True:
        # gather compact state
        state = {"cpu": read_cpu(), "mem": read_mem(), "local_accuracy": read_acc()}
        client.publish(TOPIC_STATE, json.dumps(state), qos=1)
        time.sleep(30)  # send compact summary every 30s

threading.Thread(target=telemetry_loop, daemon=True).start()

while True:
    frame = capture_frame()
    decision, score = infer(frame)
    # apply local decision modified by received global policy
    adjusted = (score >= policy["threshold"]) or (policy["lambda"] < 0.05 and score >= 0.4)
    act_on_decision(adjusted)
    time.sleep(0.01)  # maintain tight loop latency