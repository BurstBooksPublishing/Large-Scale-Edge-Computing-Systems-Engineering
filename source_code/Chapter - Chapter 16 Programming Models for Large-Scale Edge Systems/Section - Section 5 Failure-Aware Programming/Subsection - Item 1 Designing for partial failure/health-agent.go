package main

import (
  "context"
  "crypto/tls"
  "encoding/json"
  "net/http"
  "os"
  "time"

  mqtt "github.com/eclipse/paho.mqtt.golang"
)

// publishInterval and failureThreshold tuned per deployment
const (
  publishInterval   = 2 * time.Second
  failureThreshold  = 3 // consecutive failures -> degraded
  orchestratorURLEnv = "ORCHESTRATOR_URL"
  brokerURLEnv       = "BROKER_URL"
)

type HealthMsg struct {
  NodeID   string `json:"node_id"`
  Mode     string `json:"mode"`
  Load     int    `json:"load_pct"`
  Ts       int64  `json:"ts"`
}

func main() {
  broker := os.Getenv(brokerURLEnv)
  orchestrator := os.Getenv(orchestratorURLEnv)
  nodeID, _ := os.Hostname()

  opts := mqtt.NewClientOptions().AddBroker(broker).SetClientID(nodeID)
  opts.SetTLSConfig(&tls.Config{InsecureSkipVerify: false})
  client := mqtt.NewClient(opts)
  if token := client.Connect(); token.Wait() && token.Error() != nil {
    panic(token.Error())
  }
  ctx, cancel := context.WithCancel(context.Background())
  defer cancel()

  go heartbeatPublisher(ctx, client, nodeID)
  go sensorWatcher(ctx, client, orchestrator, nodeID)

  select {} // run forever; systemd or container supervisor handles exit
}

// publish periodic heartbeat
func heartbeatPublisher(ctx context.Context, client mqtt.Client, nodeID string) {
  ticker := time.NewTicker(publishInterval)
  defer ticker.Stop()
  for {
    select {
    case <-ctx.Done():
      return
    case <-ticker.C:
      m := HealthMsg{NodeID: nodeID, Mode: "full", Load: sampleLoad(), Ts: time.Now().Unix()}
      b, _ := json.Marshal(m)
      client.Publish("edge/health", 1, false, b)
    }
  }
}

// monitor a critical sensor; on repeated failures, enter degraded mode and request offload
func sensorWatcher(ctx context.Context, client mqtt.Client, orchestrator, nodeID string) {
  failures := 0
  for {
    ok := checkSensorIO(500 * time.Millisecond)
    if !ok {
      failures++
      if failures >= failureThreshold {
        // publish degraded heartbeat and call orchestrator
        m := HealthMsg{NodeID: nodeID, Mode: "degraded", Load: sampleLoad(), Ts: time.Now().Unix()}
        b, _ := json.Marshal(m)
        client.Publish("edge/health", 1, false, b)
        requestOffload(orchestrator, nodeID)
      }
    } else {
      failures = 0
    }
    time.Sleep(1 * time.Second)
  }
}

// lightweight sensor check with timeout
func checkSensorIO(timeout time.Duration) bool {
  ctx, cancel := context.WithTimeout(context.Background(), timeout)
  defer cancel()
  req, _ := http.NewRequestWithContext(ctx, "GET", "http://127.0.0.1:9000/sensor/status", nil)
  resp, err := http.DefaultClient.Do(req)
  if err != nil { return false }
  resp.Body.Close()
  return resp.StatusCode == 200
}

// notify regional orchestrator to reassign tasks
func requestOffload(orchestrator, nodeID string) {
  if orchestrator == "" { return }
  reqBody := map[string]string{"node": nodeID, "action": "offload"}
  b, _ := json.Marshal(reqBody)
  http.Post(orchestrator+"/v1/offload", "application/json", bytes.NewReader(b))
}

// sample CPU load placeholder
func sampleLoad() int { return 30 }