import multiprocessing as mp
import signal, sys, time
import cv2, numpy as np
import paho.mqtt.client as mqtt
# Placeholder import; replace with real TensorRT engine loader
# import tensorrt as trt

CAP_DEVICE = 0
QUEUE_SIZE = 4                      # admission control (prevents overload)
INFER_TIMEOUT = 0.05                # seconds per inference attempt

def capture_loop(out_q, stop_event):
    cap = cv2.VideoCapture(CAP_DEVICE)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
    while not stop_event.is_set():
        ret, frame = cap.read()
        if not ret: 
            time.sleep(0.01); continue
        try:
            out_q.put(frame, timeout=0.01)  # drop frames if queue full
        except mp.queues.Full:
            continue
    cap.release()

def preprocess(frame):
    # convert and resize once; normalize for model input
    img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (640, 480))
    img = img.astype(np.float32) / 255.0
    return np.transpose(img, (2,0,1))[None, ...]

def inference_loop(in_q, mqtt_cfg, stop_event):
    client = mqtt.Client()
    client.connect(mqtt_cfg['host'], mqtt_cfg['port'])
    client.loop_start()
    # engine = load_tensorrt_engine('model.plan')  # platform-specific
    while not stop_event.is_set():
        try:
            frame = in_q.get(timeout=0.1)
        except mp.queues.Empty:
            continue
        start = time.time()
        inp = preprocess(frame)
        # result = engine.infer(inp, timeout=INFER_TIMEOUT)  # platform API
        result = {"defect": False, "score": 0.01}  # stub for unit testing
        latency = time.time() - start
        payload = {"ts": time.time(), "latency": latency, "result": result}
        client.publish("factory/line1/analytics", str(payload), qos=1)
    client.loop_stop()
    client.disconnect()

if __name__ == "__main__":
    stop = mp.Event()
    q = mp.Queue(maxsize=QUEUE_SIZE)
    mqtt_cfg = {'host':'broker.local','port':1883}
    def handle_sigterm(*args):
        stop.set()
    signal.signal(signal.SIGTERM, handle_sigterm)
    cap_p = mp.Process(target=capture_loop, args=(q, stop))
    inf_p = mp.Process(target=inference_loop, args=(q, mqtt_cfg, stop))
    cap_p.start(); inf_p.start()
    try:
        while cap_p.is_alive() and inf_p.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        stop.set()
    cap_p.join(); inf_p.join()
    sys.exit(0)