import asyncio
import cv2
import psutil
import time
import onnxruntime as ort

MODEL_PATH = "/opt/models/inspector.onnx"  # production model path
TARGET_UTIL = 0.75                            # target CPU/GPU utilization
MAX_QUEUE = 8                                 # local buffer threshold

# initialize runtime (uses CUDAExecutionProvider if available)
sess = ort.InferenceSession(MODEL_PATH, providers=["CUDAExecutionProvider","CPUExecutionProvider"])

async def capture_loop(queue, device=0):
    cap = cv2.VideoCapture(device)
    fps = 30.0
    while True:
        start = time.time()
        ret, frame = cap.read()
        if not ret:
            await asyncio.sleep(0.01); continue
        if queue.qsize() < MAX_QUEUE:
            await queue.put((frame, time.time()))
        else:
            # drop or downsample to reduce load
            pass
        # sleep to respect adaptive fps
        await asyncio.sleep(max(0, 1.0/fps - (time.time()-start)))

async def monitor_and_control(queue):
    fps_target = 30.0
    while True:
        cpu = psutil.cpu_percent(interval=0.5)
        qlen = queue.qsize()
        # simple controller: reduce fps if CPU or queue high
        if cpu > TARGET_UTIL*100 or qlen > MAX_QUEUE*0.75:
            fps_target = max(5.0, fps_target * 0.8)   # reduce rate
        else:
            fps_target = min(30.0, fps_target * 1.05) # increase rate
        # publish new fps to capture loop via shared state (omitted for brevity)
        await asyncio.sleep(0.5)

async def infer_loop(queue):
    while True:
        frame, t0 = await queue.get()
        # preprocess (resize, normalize) - minimal overhead
        img = cv2.resize(frame, (320, 320))
        inp = img.transpose(2,0,1).astype('float32')[None]/255.0
        # model inference
        out = sess.run(None, {sess.get_inputs()[0].name: inp})
        # postprocess and actuation decision (omitted)
        queue.task_done()

async def main():
    q = asyncio.Queue()
    await asyncio.gather(capture_loop(q), infer_loop(q), monitor_and_control(q))

if __name__ == "__main__":
    asyncio.run(main())