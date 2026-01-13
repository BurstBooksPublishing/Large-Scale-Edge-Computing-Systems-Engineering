#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 

// Simple bounded queue for backpressure
template
class BoundedQueue {
  std::mutex m; std::condition_variable cv;
  std::queue q; size_t cap;
public:
  BoundedQueue(size_t c):cap(c){}
  bool push(T v, int timeout_ms); // block/timeout on full
  bool pop(T &out);               // block until available
};

// Event descriptor carrying id and payload pointer
struct Event {
  uint64_t id; // monotonic per-source id
  int fd;      // source file descriptor
  std::vector payload;
};

// Worker thread: idempotent processing; persist processed id periodically.
void workerLoop(BoundedQueue &in, std::atomic &run,
                std::unordered_set &processed, std::mutex &pm) {
  while (run) {
    Event ev;
    if (!in.pop(ev)) continue;
    { std::lock_guard lg(pm);
      if (processed.count(ev.id)) continue; // dedupe
      processed.insert(ev.id);
    }
    // Application-specific short handler; avoid long blocking here.
    // e.g., run small inference, emit control command.
    processPayload(ev.payload.data(), ev.payload.size());
    // durable commit of processed.id can be batched to flash/db.
    commitProgressAsync(ev.id);
  }
}

// Reactor: epoll waits for ready fds and enqueues parsed events.
int main() {
  int ep = epoll_create1(0);
  // register listening sockets from sensors, broker, etc.
  // set non-blocking, add with EPOLLIN | EPOLLET
  BoundedQueue queue(1024); // tunable capacity
  std::atomic run{true};
  std::unordered_set processed;
  std::mutex pm;
  std::vector workers;
  for (int i=0;i<4;++i) workers.emplace_back(workerLoop,
                       std::ref(queue), std::ref(run),
                       std::ref(processed), std::ref(pm));
  struct epoll_event events[64];
  while (run) {
    int n = epoll_wait(ep, events, 64, 1000);
    for (int i=0;i
\subsection{Item 2:  Reactive and asynchronous processing}
Reactive processing extends event-driven handlers into a disciplined, nonblocking architecture that emphasizes responsiveness, resilience, elasticity, and message-driven composition. The previous discussion of event-driven semantics established the decoupling foundation used here to reason about asynchronous pipelines across heterogeneous edge nodes.

Concept: reactive and asynchronous processing decouples producers and consumers with explicit flow control. Producers emit events or futures. Consumers process without blocking kernel threads. Backpressure propagates capacity limits upstream. This model suits constrained SoCs such as ARM Cortex-A/R, NVIDIA Jetson, and platforms running Linux, Zephyr, or FreeRTOS. Popular runtimes and frameworks include Tokio (Rust), libuv/node (Node.js), Akka Typed (JVM), and async IO via epoll or io_uring on modern Linux kernels.

Theory: model an asynchronous service as a pool of $c$ workers, each with service rate $\mu$ events per second, and an aggregate arrival rate $\lambda$. Stability requires offered load below capacity,
\begin{equation}[H]\label{eq:stability}
\lambda < c\mu,
\end{equation}
otherwise queues grow unbounded. Define utilization $\rho=\lambda/(c\mu)$. Little's law links expected in-system items $E[N]$ to latency $E[T]$,
\begin{equation}[H]\label{eq:littles}
E[N]=\lambda E[T].
\end{equation}
For provisioning, choose $c \ge \lceil \lambda/\mu \rceil$. Bounded-queue designs introduce additional loss or backpressure; with queue capacity $Q$ the probability of reject rises when instantaneous load exceeds $c\mu$ and queue fills. Implementing backpressure as a feedback control reduces effective arrival rate $\lambda_{\text{eff}}$ to meet (1). For latency-critical pipelines, shape arrivals using token-bucket policing at ingress or use adaptive admission that measures $E[T]$ and throttles when $E[T]$ crosses SLO thresholds.

Example: industrial vibration sensors stream feature vectors to a regional Jetson Xavier NX for anomaly scoring. The pipeline uses MQTT for telemetry, a bounded async queue at the aggregator, and a worker pool running an optimized PyTorch Mobile or TensorRT model. Reactive design choices:
- Use MQTT QoS 1 for delivery and enable TLS for confidentiality.
- Apply bounded in-process queues sized to fit memory and SLO jitter.
- Propagate backpressure by acknowledging MQTT later or dropping least-recent events under overload.

A minimal production-ready Rust/Tokio implementation demonstrating a bounded async pipeline and MQTT ingestion follows. It uses rumqttc for MQTT, a bounded mpsc channel for backpressure, and a fixed worker pool. Replace placeholders with device-specific configuration and credentials.

\begin{lstlisting}[language=Rust,caption={Async MQTT ingestion with bounded worker pool (Tokio + rumqttc).},label={lst:async_mqtt}]
use rumqttc::{AsyncClient, MqttOptions, QoS};
use tokio::{sync::mpsc, task};
use std::time::Duration;

// Configuration constants (tune per-device)
const MQTT_BROKER: &str = "mqtt.example.local:8883";
const TOPIC: &str = "factory/sensors/vibration";
const CHANNEL_CAPACITY: usize = 256; // bounded queue for backpressure
const WORKERS: usize = 4;

#[tokio::main(flavor = "multi_thread", worker_threads = 4)]
async fn main() -> anyhow::Result<()> {
    // MQTT client setup with TLS and keepalive tuned for edge links.
    let mut mqttoptions = MqttOptions::new("edge-node-01", "mqtt.example.local", 8883);
    mqttoptions.set_keep_alive(Duration::from_secs(30));
    // mqttoptions.set_transport(... TLS config ...);

    let (client, mut eventloop) = AsyncClient::new(mqttoptions, 10);
    client.subscribe(TOPIC, QoS::AtLeastOnce).await?;

    // Bounded channel implements local backpressure.
    let (tx, mut rx) = mpsc::channel::>(CHANNEL_CAPACITY);

    // Spawn MQTT event loop forwarder.
    let tx_clone = tx.clone();
    task::spawn(async move {
        loop {
            match eventloop.poll().await {
                Ok(notification) => {
                    if let rumqttc::Event::Incoming(rumqttc::Packet::Publish(p)) = notification {
                        // Best-effort send; drop if channel full to avoid blocking.
                        let _ = tx_clone.try_send(p.payload.to_vec());
                    }
                }
                Err(err) => {
                    // Log and backoff; in production integrate exponential backoff and alerting.
                    eprintln!("MQTT eventloop error: {:?}", err);
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }
            }
        }
    });

    // Spawn fixed worker pool for model inference or processing.
    for _ in 0..WORKERS {
        let mut rx_worker = rx.clone();
        task::spawn(async move {
            while let Some(payload) = rx_worker.recv().await {
                // Process payload (parse, preprocess, inference, persist).
                process_payload(payload).await;
            }
        });
    }

    // Keep main alive; implement graceful shutdown hooks in real deployment.
    futures::future::pending::<()>().await;
    // unreachable
}

async fn process_payload(_data: Vec) {
    // Placeholder: deserialize, run model, emit alert. Keep CPU-bound work off async threads.
    // Use tokio::task::spawn_blocking for heavy CPU kernels or call native libraries.
    tokio::task::spawn_blocking(move || {
        // CPU-bound inference or signal processing here.
    }).await.ok();
}