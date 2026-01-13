package main

import (
        "crypto/tls"
        "log"
        "math"
        "sync/atomic"
        "time"

        mqtt "github.com/eclipse/paho.mqtt.golang"
)

// Simple EWMA estimator for mean inter-arrival and variance.
type ewma struct {
        alpha float64
        mean  float64
        var2  float64
        inited bool
}
func (e *ewma) Update(x float64) {
        if !e.inited {
                e.mean = x; e.var2 = 0; e.inited = true; return
        }
        d := x - e.mean
        e.mean += e.alpha * d
        e.var2 = (1 - e.alpha)*(e.var2 + e.alpha*d*d) // approximate var
}
func (e *ewma) Std() float64 { return math.Sqrt(e.var2) }

var lastRecv int64 // unix nanos

func main() {
        opts := mqtt.NewClientOptions().
                AddBroker("tls://mqtt-broker.example:8883").
                SetClientID("edge-detector-01")
        tlsCfg := &tls.Config{MinVersion: tls.VersionTLS12}
        opts.SetTLSConfig(tlsCfg)

        client := mqtt.NewClient(opts)
        if token := client.Connect(); token.Wait() && token.Error() != nil {
                log.Fatalf("connect: %v", token.Error())
        }

        est := &ewma{alpha: 0.1}
        const topic = "edge/heartbeat/+/status"
        client.Subscribe(topic, 1, func(c mqtt.Client, m mqtt.Message) {
                // parse arrival timestamp if present; otherwise use local receive time
                now := time.Now().UnixNano()
                prev := atomic.SwapInt64(&lastRecv, now)
                if prev == 0 { return }
                ia := float64(now - prev) / 1e9 // inter-arrival seconds
                est.Update(ia)
        })

        // periodic failure check: mean + k*std
        ticker := time.NewTicker(200 * time.Millisecond)
        defer ticker.Stop()
        const kfloat = 6.0
        for range ticker.C {
                prev := atomic.LoadInt64(&lastRecv)
                if prev == 0 { continue }
                elapsed := float64(time.Now().UnixNano()-prev)/1e9
                threshold := est.mean + kfloat*est.Std() + 0.05 // safety floor
                if elapsed > threshold {
                        // actionable alert: mark node unhealthy, notify orchestrator
                        log.Printf("failure detected: elapsed=%.3fs thr=%.3fs", elapsed, threshold)
                        // integrate: call kubelet API, update etcd, or publish to control topic
                }
        }
}