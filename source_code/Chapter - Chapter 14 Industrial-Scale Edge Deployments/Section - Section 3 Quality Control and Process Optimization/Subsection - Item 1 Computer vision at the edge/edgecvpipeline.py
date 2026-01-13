#!/usr/bin/env python3
# Production-ready, minimal-dependency pipeline using OpenCV and ONNX Runtime.
import cv2, time, queue, threading, paho.mqtt.client as mqtt, onnxruntime as ort

# Configure runtime with preferred providers (TensorRT, OpenVINO, CPU fallback)
sess_opts = ort.SessionOptions()
sess = ort.InferenceSession("model.onnx", sess_options=sess_opts,
                            providers=["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"])

cap = cv2.VideoCapture("v4l2:///dev/video0")  # use GStreamer string for industrial cameras
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

in_q = queue.Queue(maxsize=4); out_q = queue.Queue(maxsize=8)
mqttc = mqtt.Client(); mqttc.connect("broker.local", 1883, 60)

def capture_loop():
    while True:
        ret, frame = cap.read()
        if not ret: break
        if not in_q.full(): in_q.put((time.time(), frame))

def worker_loop():
    while True:
        ts, frame = in_q.get()
        # Preprocess: resize, normalize, reorder to NCHW
        img = cv2.resize(frame, (320,320))
        img = img[:,:,::-1].transpose(2,0,1).astype("float32")/255.0
        img = img.reshape(1,3,320,320)
        # Inference
        start = time.time()
        outputs = sess.run(None, {sess.get_inputs()[0].name: img})
        latency = time.time() - start
        # Postprocess: decode detections (domain specific)
        detections = outputs[0]
        out_q.put({"ts": ts, "latency": latency, "detections": detections})

def publish_loop():
    while True:
        item = out_q.get()
        payload = {
            "timestamp": item["ts"],
            "infer_ms": int(item["latency"]*1000),
            "count": int(len(item["detections"]))  # example
        }
        mqttc.publish("factory/line1/vision/results", str(payload), qos=1)

# Start threads
threads = [threading.Thread(target=capture_loop, daemon=True),
           threading.Thread(target=worker_loop, daemon=True),
           threading.Thread(target=publish_loop, daemon=True)]
for t in threads: t.start()
for t in threads: t.join()